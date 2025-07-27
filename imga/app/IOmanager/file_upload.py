import os
import uuid
import shutil
import zipfile
from datetime import datetime
from IOmanager.meta_manager import MetaManager

class FileUploader:
    def __init__(self, temp_dir, raw_dir, meta_path):
        self.temp_pdf_dir = os.path.join(temp_dir, "pdf")
        self.temp_zip_dir = os.path.join(temp_dir, "zip")
        self.raw_dir = raw_dir
        self.meta = MetaManager(meta_path)

        os.makedirs(self.temp_pdf_dir, exist_ok=True)
        os.makedirs(self.temp_zip_dir, exist_ok=True)
        os.makedirs(self.raw_dir, exist_ok=True)

    def generate_code_filename(self):
        return uuid.uuid4().hex[:8] + ".pdf"

    def upload_files(self, upload_files, project="default", group_id="default_group", skip_existing=True):
        file_records = []
        skipped_files = []
        existing_metas = self.meta.load_batch_meta()

        # 기존 등록된 파일명 모음
        if skip_existing:
            existing_files = set(m.get("org_filename") for m in existing_metas)
        else:
            existing_files = set()

        for file in upload_files:
            filename = os.path.basename(file.name)

            # 중복 방지 (project + file 기준)
            if any(filename in m.get("original_file_ids") and m.get("project") == project for m in existing_metas):
                skipped_files.append(filename)
                continue

            ext = os.path.splitext(filename)[1].lower()

            if ext == ".zip":
                saved_zip_path = os.path.join(self.temp_zip_dir, filename)
                shutil.copy(file.name, saved_zip_path)
                with zipfile.ZipFile(saved_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(self.temp_pdf_dir)
                os.remove(saved_zip_path)

            elif ext == ".pdf":
                saved_pdf_path = os.path.join(self.temp_pdf_dir, filename)
                shutil.copy(file.name, saved_pdf_path)

        for temp_pdf in os.listdir(self.temp_pdf_dir):
            if not temp_pdf.lower().endswith(".pdf"):
                continue

            org_filename = temp_pdf
            if org_filename in existing_files:
                os.remove(os.path.join(self.temp_pdf_dir, temp_pdf))
                skipped_files.append(org_filename)
                continue

            code_filename = self.generate_code_filename()
            raw_pdf_path = os.path.join(self.raw_dir, code_filename)
            shutil.move(os.path.join(self.temp_pdf_dir, temp_pdf), raw_pdf_path)

            # 기록
            self.meta.save_file_code(org_filename, code_filename)

            file_record = {
                "project": project,
                "org_filename": org_filename,
                "code_filename": code_filename,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            file_records.append(file_record)

        return file_records, skipped_files
