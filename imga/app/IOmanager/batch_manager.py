import os
import json
import time
import base64
import httpx
import ssl
import shutil
import gc
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from processor.pre_processor import PreProcess
from config.config import PAGE_TYPE_MAPPING, PROMPT_MAPPING
from IOmanager.meta_manager import MetaManager
from concurrent.futures import ThreadPoolExecutor, as_completed


ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

class BatchManager:
    def __init__(self, api_key, result_dir, image_dir, raw_dir, meta_path):
        self.client = OpenAI(api_key=api_key, http_client=httpx.Client(verify=False))
        self.batch_result_dir = result_dir
        self.image_dir = image_dir
        self.raw_dir = raw_dir
        self.preprocessor = PreProcess(max_workers=4)
        self.meta = MetaManager(meta_path)

        os.makedirs(self.batch_result_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)

    def detect_page_type(self, page_number):
        for page_type, pages in PAGE_TYPE_MAPPING.items():
            if page_number in pages:
                return page_type
        return "unknown"

    def _group_images_by_page_type(self, images):
        grouped = defaultdict(list)
        for img_path in images:
            filename = os.path.basename(img_path)
            page_num = int(filename.split("_")[1])
            page_type = self.detect_page_type(page_num)
            if page_type == "exclude":
                continue
            grouped[page_type].append(img_path)
        return grouped

    def _make_jsonl(self, images, page_type, batch_id):
        jsonl_path = os.path.join(self.image_dir, f"{page_type}_{batch_id}_request.jsonl")
        prompt_text = PROMPT_MAPPING[page_type]
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for img_path in images:
                custom_id = os.path.basename(img_path).split('.')[0]
                with open(img_path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode("utf-8")
                entry = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4.1",
                        "messages": [
                            {"role": "user", "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
                            ]}
                        ],
                        "temperature": 0.3,
                        "top_p": 0.8
                    }
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return jsonl_path

    def _submit_batch_for_page_type(self, page_type, items, batch_group_id, project):
        images = [img for img, _, _ in items]
        jsonl_path = self._make_jsonl(images, page_type, batch_group_id)

        file = self.client.files.create(file=open(jsonl_path, "rb"), purpose="batch")
        
        batch = self.client.batches.create(
            input_file_id=file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"project": project, "page_type": page_type, "batch_group_id": batch_group_id}
        )

        self.meta.upsert_batch_meta(
            project_name=project,
            batch_id=batch.id,
            page_type=page_type,
            group_id=batch_group_id,
            status="submitted",
            file_ids=list(set([code_filename for _, code_filename, _ in items])),
            org_file_ids=list(set([org_filename for _, _, org_filename in items]))
        )
        time.sleep(0.1)
            
        
        print(f"[Batch Submitted] page_type: {page_type} | {len(images)} pages → Batch ID: {batch.id}")

    def submit_multi_pdf_batch(self, pdf_list, batch_group_id, project):
        batch_cache = defaultdict(list)

        for org_filename, code_filename in pdf_list:
            pdf_path = os.path.join(self.raw_dir, code_filename)
            save_dir = os.path.join(self.image_dir, code_filename)
            os.makedirs(save_dir, exist_ok=True)

            self.preprocessor.pdf_to_image(pdf_path, save_dir)
            images = [os.path.join(save_dir, f) for f in os.listdir(save_dir) if f.endswith('.png')]
            os.remove(pdf_path)

            grouped_images = self._group_images_by_page_type(images)
            for page_type, imgs in grouped_images.items():
                for img in imgs:
                    batch_cache[page_type].append((img, code_filename, org_filename))
                    

        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(self._submit_batch_for_page_type, page_type, items, batch_group_id, project)
                for page_type, items in batch_cache.items()
            ]
            for f in futures:
                f.result()

        for _, code_filename in pdf_list:
            shutil.rmtree(os.path.join(self.image_dir, code_filename), ignore_errors=True)

        print(f"Garbage collector: collected {gc.collect()} unreachable objects.")

    def _write_batch_output(self, batch_id, output_file_id, result_path):
        trial = 0
        while not os.path.exists(result_path) and trial < 3:
            try:
                content = self.client.files.content(output_file_id).text
                with open(result_path, "a", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                break
            except Exception as e:
                trial += 1
                time.sleep(1)
                print(f"[Retry] Downloading output for {batch_id}, attempt {trial}")
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _check_single_batch(self, batch):
        batch_id = batch["batch_id"]
        response = self.client.batches.retrieve(batch_id=batch_id)
        
        complete_count = response.request_counts.completed
        total_count = response.request_counts.total
        new_status = response.status
        
        if (new_status == "completed") & (complete_count != total_count):
            new_status = "failed"
            
        batch["status"] = new_status
        batch["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"↪ batch_id: {batch_id} → {new_status}")

        if new_status == "completed":
            result_path = os.path.join(self.batch_result_dir, f"{batch['project']}_{batch_id}_response.jsonl")
            self._write_batch_output(batch_id, response.output_file_id, result_path)

            if os.path.exists(result_path):
                raw_files = batch.get("file_ids", [])
                for code_filename in raw_files:
                    raw_pdf_path = os.path.join(self.raw_dir, code_filename)
                    if os.path.exists(raw_pdf_path):
                        os.remove(raw_pdf_path)
                        print(f"[Deleted] Raw PDF: {raw_pdf_path}")
        return batch

    def check_batches(self):
        print("[Batch Status Check]")
        batch_metas = self.meta.load_batch_meta()

        with ThreadPoolExecutor(max_workers=18) as executor:
            futures = [
                executor.submit(self._check_single_batch, batch)
                for batch in batch_metas
                if batch["status"] not in {"finish", "failed", "cancelled", "completed"}
            ]
            updated_batches = [batch for batch in batch_metas if batch["status"] in {"finish", "failed", "cancelled", "completed"}]
            for future in as_completed(futures):
                updated_batches.append(future.result())

        with open(self.meta.batch_meta_path, "w", encoding="utf-8") as f:
            for batch in updated_batches:
                f.write(json.dumps(batch, ensure_ascii=False) + "\n")



    def rerun(self, retry=3, delay=1):
        print("[Retry Check] Verifying missing result files...")

        # 1. 메타 파일에서 completed 상태 batch 목록
        batch_metas = self.meta.load_batch_meta()
        
        completed_batches = [
                line for line in batch_metas
                if "completed" in line['status']
            ]
        

        # 2. 실제 저장된 결과 파일 목록 (파일명 기준)   
        existing_result_files = {
                f"batch_{filename.split("_")[-2]}"  # → batch_id
                for filename in os.listdir(self.batch_result_dir)
                if filename.endswith(".jsonl") and len(filename.split("_")) > 1
            }
            # 3. 누락된 batch_id들
        missing_batches = [
                b for b in completed_batches
                if b['batch_id']  not in existing_result_files
            ]
        print(f"→ {len(missing_batches)} batch(es) missing result files")

        # 4. 재시도 처리
        for batch in missing_batches:
            batch_id = batch["batch_id"]
            result_path = os.path.join(self.batch_result_dir, f"{batch['project']}_{batch_id}_response.jsonl")
            batch = self._check_single_batch(batch)
            if not batch:
                print(f"[Skip] Missing output_file_id for batch {batch_id}")
                continue
        
        with open(self.meta.batch_meta_path, "w", encoding="utf-8") as f:
            for b in batch_metas:
                for updated in missing_batches:
                    if b["batch_id"] == updated["batch_id"]:
                        b["status"] = updated["status"]
                        b["last_updated_at"] = updated.get("last_updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                f.write(json.dumps(b, ensure_ascii=False) + "\n")

            # print(f"[Retry] Rewriting result for batch {batch_id}")
            # retry_func(batch_id, output_file_id, result_path)
            
    def retry_failed_batches(self):
        """
        실패한 배치들을 기존 jsonl로 다시 제출하고, 메타데이터 갱신
        """
        batch_metas = self.meta.load_batch_meta()
        failed_batches = [b for b in batch_metas if b["status"] == "failed"]

        for batch in failed_batches:
            old_batch_id = batch["batch_id"]
            project = batch["project"]
            page_type = batch["page_type"]
            batch_group_id = batch["group_id"]
            jsonl_path = os.path.join(self.image_dir, f"{page_type}_{batch_group_id}_request.jsonl")
            if not os.path.exists(jsonl_path) or os.path.getsize(jsonl_path) == 0:
                print(f"❌ JSONL 파일 없음 또는 비어있음: {jsonl_path}")
                continue

            # 이미지, 코드파일, 원본 파일 매핑
            items = [
                (os.path.join(self.image_dir, code_filename), code_filename, org_filename)
                for code_filename, org_filename in zip(batch["file_ids"], batch["original_file_ids"])
            ]

            try:
                with open(jsonl_path, "rb") as f:
                    file = self.client.files.create(file=f, purpose="batch")

                new_batch = self.client.batches.create(
                    input_file_id=file.id,
                    endpoint="/v1/chat/completions",
                    completion_window="24h",
                    metadata={"project": project, "page_type": page_type, "batch_group_id": batch_group_id}
                )

                # 기존 실패 메타 제거 후 새로 삽입
                self.meta.remove_batch_meta(batch_id=old_batch_id)
                self.meta.upsert_batch_meta(
                    project_name=project,
                    batch_id=new_batch.id,
                    page_type=page_type,
                    group_id=batch_group_id,
                    status="submitted",
                    file_ids=list(set([code_filename for _, code_filename, _ in items])),
                    org_file_ids=list(set([org_filename for _, _, org_filename in items]))
                )

                print(f"✅ [Retry Submitted] {jsonl_path} → New Batch ID: {new_batch.id}")

            except Exception as e:
                print(f"❌ Batch 재제출 실패 (Old ID: {old_batch_id}): {e}")
