import os
import json
from datetime import datetime

class MetaManager:
    def __init__(self, meta_path):
        os.makedirs(meta_path, exist_ok=True)
        # 메타 저장 경로 기준으로 batch_meta, file_codes 경로 설정
        self.batch_meta_path = os.path.join(meta_path, "batch_meta.jsonl")
        self.file_codes_path = os.path.join(meta_path, "file_codes.json")
                # file_codes.json 파일이 없으면 빈 JSON으로 생성
        if not os.path.exists(self.file_codes_path):
            open(self.file_codes_path, "w", encoding="utf-8").close()
                

        # batch_meta.jsonl 파일이 없으면 빈 파일 생성
        if not os.path.exists(self.batch_meta_path):
            open(self.batch_meta_path, "w", encoding="utf-8").close()

        
    def load_batch_meta(self):
        # batch_meta.jsonl 로딩
        if os.path.exists(self.batch_meta_path):
            try:
                with open(self.batch_meta_path, "r", encoding="utf-8") as f:
                    return [json.loads(line) for line in f]
                
            except json.JSONDecodeError:
                print(f"⚠️ Error decoding JSON in {self.batch_meta_path}. Attempting to auto-fix...")
                self._auto_fix_batch_meta()
                return self.load_batch_meta()
        return []

    def save_batch_meta(self, metas):
        # batch_meta.jsonl 저장
        with open(self.batch_meta_path, "w", encoding="utf-8") as f:
            for meta in metas:
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    def upsert_batch_meta(
        self,
        batch_id,
        project_name=None,
        page_type=None,
        group_id=None,
        status=None,
        file_ids=None,
        org_file_ids=None
    ):
        """
        batch_meta.jsonl에 기록 추가 또는 갱신
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metas = self.load_batch_meta()
        found = False

        # 업데이트할 필드 목록
        update_fields = {
            "project": project_name,
            "page_type": page_type,
            "group_id": group_id,
            "status": status,
            "file_ids": file_ids,
            "original_file_ids": org_file_ids,
        }

        for meta in metas:
            if meta["batch_id"] == batch_id:
                # 기존 레코드 업데이트
                changed = False
                for key, value in update_fields.items():
                    if value is not None and meta.get(key) != value:
                        meta[key] = value
                        changed = True
                if changed:
                    meta["last_updated_at"] = now
                found = True

        # 새 레코드 추가 (모든 필수 필드가 있을 때만)
        required_keys = ["project", "page_type", "group_id", "status", "file_ids", "original_file_ids"]
        if not found and all(update_fields.get(k) is not None for k in required_keys):
            metas.append({
                "batch_id": batch_id,
                **{k: update_fields[k] for k in required_keys},
                "created_at": now,
                "last_updated_at": now
            })

        self.save_batch_meta(metas)

    def save_file_code(self, org_filename, code_filename):
        """
        file_codes.json에 원본/코드 파일명 한 줄 추가 저장
        """
        info = {"org_filename": org_filename, "code_filename": code_filename}
        with open(self.file_codes_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(info, ensure_ascii=False) + "\n")


    def remove_batch_meta(self, batch_id: str):
        temp_path = self.batch_meta_path + ".tmp"
        with open(self.batch_meta_path, "r", encoding="utf-8") as f_in, \
            open(temp_path, "w", encoding="utf-8") as f_out:
            for line in f_in:
                try:
                    data = json.loads(line)
                    if data.get("batch_id") != batch_id:
                        f_out.write(json.dumps(data, ensure_ascii=False) + "\n")
                except:
                    continue  # Skip malformed lines

        os.replace(temp_path, self.batch_meta_path)
        print(f"🗑️ Removed failed batch_id: {batch_id} from meta.")
        
        
    def _auto_fix_batch_meta(self):
        """
        batch_meta.jsonl에서 잘못된 레코드 자동 수정
        """
        with open(self.batch_meta_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 백업 경로 안전하게 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(self.batch_meta_path)
        bk_path = f"{base}_{timestamp}.bak"

        with open(bk_path, "w", encoding="utf-8") as f_bk:
            f_bk.writelines(lines)

        # 역순으로 검사하여 마지막 정상 JSON 찾기
        for i in range(len(lines) - 1, -1, -1):
            try:
                json.loads(lines[i])
                # 그 줄까지 유지
                lines = lines[:i + 1]
                break
            except json.JSONDecodeError:
                continue

        with open(self.batch_meta_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"✅ Fixed JSONL by trimming to {len(lines)} lines.")
        print(f"🛡️ Backup saved at: {bk_path}")