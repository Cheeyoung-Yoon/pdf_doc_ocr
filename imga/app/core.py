import os
import time
from IOmanager.file_upload import FileUploader
from IOmanager.batch_manager import BatchManager
from IOmanager.meta_manager import MetaManager
from processor.post_processor import PostProcessor
import subprocess

class Core:
    def __init__(self, upload_temp_dir, raw_dir, meta_path, result_dir, image_dir, api_key):
        self.meta = MetaManager(meta_path)
        self.uploader = FileUploader(upload_temp_dir, raw_dir, meta_path)
        self.meta_path = meta_path
        self.result_dir = result_dir
        self.manager = BatchManager(
            api_key=api_key,
            result_dir=os.path.join(os.path.dirname(meta_path), "batch_results"),
            image_dir=image_dir,
            raw_dir=raw_dir,
            meta_path=meta_path
        )
        self.processor = PostProcessor(
            batch_meta_path=os.path.join(meta_path, "batch_meta.jsonl"),
            file_code_path=os.path.join(meta_path, "file_codes.json"),
            result_root=self.result_dir,
            output_dir=os.path.join(self.result_dir, "output"),
            meta_path=self.meta_path
        )

    # [1] 파일 업로드
    def upload_files(self, upload_files, project, group_id="default_group"):
        file_records = self.uploader.upload_files(upload_files, project, group_id)
        print(f"✅ Uploaded")
        return file_records

    # [2] batch 실행
    def execute_batch_process(self, pdf_list_chunk, project):
        if not pdf_list_chunk:
            print("✅ No input chunk received.")
            return

        group_id = f"default_group_chunk_{int(time.time())}"
        print(f"🚀 Submitting batch group: {group_id} (size: {len(pdf_list_chunk)})")

        self.manager.submit_multi_pdf_batch(
            pdf_list=pdf_list_chunk,
            batch_group_id=group_id,
            project=project
        )

    # [4] batch 상태 업데이트
    def status_update(self):
        self.manager.check_batches()
        print("✅ Batch status updated.")
        time.sleep(2)
        self.manager.rerun()
        print("✅ Batch rerun completed.")
        self.manager.retry_failed_batches()
        print("✅ Retried failed batches.")

    # [5] 전체 batch 메타 상태 조회
    def get_status(self):
        return self.meta.load_batch_meta()

    # [6] 후처리 실행
    def postprocess_results(self):

        print("🚀 Starting postprocessor...")
        subprocess.Popen(["python", "./app/post_processor_run.py"])
        print("✅ Postprocessing complete.")


