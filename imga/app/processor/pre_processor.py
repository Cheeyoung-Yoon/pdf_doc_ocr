import cv2
import numpy as np
import os
import fitz
from concurrent.futures import ThreadPoolExecutor

class PreProcess:
    # 하이퍼파라미터 상수 정의
    CROP_OVERLAP = 60      # 슬라이딩 윈도우 겹침 영역
    CROP_TOP = 200           # 위쪽 자르기 여백
    CROP_BOTTOM = 300        # 아래쪽 자르기 여백
    INDEX_OFFSET = 7         # 저장 파일명에 사용할 페이지 보정 인덱스

    def __init__(self, max_workers=4):
        # 병렬 처리에 사용할 최대 쓰레드 수
        self.max_workers = max_workers

    @staticmethod
    def pixmap_to_np(pix):
        """
        fitz의 Pixmap 객체를 NumPy 이미지 배열로 변환
        RGBA → BGR, RGB → BGR 로 변환
        """
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            return cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        return img_np

    @staticmethod
    def clean_and_crop_binary_image_cv2_from_np(img_np):
        """
        이미지 이진화 → 노이즈 제거 → 테이블 구조 강화 → 내용만 자동 Crop
        """
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 내용이 흰색이 되도록 반전
        inverted = 255 - binary

        # 닫힘 연산으로 끊긴 선/획 연결
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (4, 4))
        filled = cv2.morphologyEx(inverted, cv2.MORPH_CLOSE, kernel_close, iterations=1)

        # 테이블 선 강조 (세로/가로 커널)
        kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 4))
        kernel_horz = cv2.getStructuringElement(cv2.MORPH_RECT, (4, 1))
        filled = cv2.dilate(filled, kernel_vert, iterations=1)
        filled = cv2.dilate(filled, kernel_horz, iterations=1)

        # 작은 점 노이즈 제거
        kernel_dot = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cleaned = cv2.morphologyEx(filled, cv2.MORPH_OPEN, kernel_dot, iterations=1)

        # 다시 흑백 반전 (텍스트 = 검정)
        enhanced_binary = 255 - cleaned

        # 자동 Crop (내용이 있는 좌표 영역만 잘라냄)
        coords = cv2.findNonZero(255 - enhanced_binary)
        if coords is None:
            return enhanced_binary
        x, y, w, h = cv2.boundingRect(coords)
        binary_cropped = enhanced_binary[
            y + PreProcess.CROP_TOP : y + h - PreProcess.CROP_BOTTOM, x : x + w
        ]
        return binary_cropped

    @staticmethod
    def vertical_sliding_window(img, out_path, overlap=None):
        """
        세로 방향 슬라이딩 윈도우로 이미지 3등분 저장 (겹침 포함)
        """
        if overlap is None:
            overlap = PreProcess.CROP_OVERLAP

        h, w = img.shape[:2]
        adj_out_path, extension = os.path.splitext(out_path)

        n_splits = 3
        step = (h + overlap * (n_splits - 1)) // n_splits

        for order in range(n_splits):
            y_start = max(0, order * step - order * overlap)
            y_end = min(h, y_start + step)
            crop = img[y_start:y_end, :]
            crop_out_path = adj_out_path + f"_crop_{order}" + extension
            cv2.imwrite(crop_out_path, crop)

    def process_page(self, pdf_path, page_idx, output_dir, zoom):
        """
        PDF 한 페이지 처리: 렌더링 → 이진화 → Crop → 이미지 저장
        """
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_idx)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        file_name = os.path.basename(pdf_path).split('.')[0]

        # PDF 페이지를 NumPy 이미지로 변환
        img_np = self.pixmap_to_np(pix)

        # 이진화 및 내용 Crop
        cleaned_img = self.clean_and_crop_binary_image_cv2_from_np(img_np)

        # 좌/우 반으로 나누기
        h, w = cleaned_img.shape
        mid = w // 2
        left_half = cleaned_img[:, :mid]
        right_half = cleaned_img[:, mid:]

        # 페이지 인덱스 보정 후 파일명 생성
        left_idx = 2 * (page_idx + 1) - 1 + self.INDEX_OFFSET
        right_idx = 2 * (page_idx + 1) + self.INDEX_OFFSET

        out_path_left = os.path.join(output_dir, f"{file_name}_{left_idx:02d}.png")
        out_path_right = os.path.join(output_dir, f"{file_name}_{right_idx:02d}.png")

        # 좌/우 각각 슬라이딩 저장
        self.vertical_sliding_window(left_half, out_path_left)
        self.vertical_sliding_window(right_half, out_path_right)

    def pdf_to_image(self, pdf_path, output_dir, dpi=400):
        """
        전체 PDF 페이지를 이미지로 변환 + 전처리 수행
        """
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        zoom = dpi / 72  # DPI 기준 확대 배율 계산
        os.makedirs(output_dir, exist_ok=True)

        # 병렬 처리 실행
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.process_page, pdf_path, i, output_dir, zoom)
                for i in range(total_pages)
            ]
            for future in futures:
                future.result()  # 예외 발생 시 여기서 throw
