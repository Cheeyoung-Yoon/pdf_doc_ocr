import os
import sys
os.environ.pop("SSL_CERT_FILE", None)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
import gradio as gr
from core import Core
import config.config as config
import pandas as pd
from math import ceil
import tempfile
import shutil

core = Core(
    upload_temp_dir="./data/temp",
    raw_dir=config.PDF_DIR,
    meta_path=config.META_DIR,
    result_dir=config.RESULT_DIR,
    image_dir=config.IMAGE_DIR,
    api_key=config.OPENAI_API_KEY
)

def clean_temp_dir(folder_path = "./pre_process"):
    files = len(os.listdir(folder_path))
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)         # 파일 또는 링크
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)     # 서브폴더 전체 삭제
        except Exception as e:
            print(f"삭제 실패: {file_path} - {e}")
    return f"✅ {files} of Temp files removed."

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

# --------------------------
# [1] 파일 업로드 → Batch 실행
# --------------------------

def upload_files_and_batch(upload_files, project):
    if not upload_files:
        return "❌ No files uploaded."

    file_records, skipped_files = core.upload_files(upload_files,project)
    code_files = [(r["org_filename"], r["code_filename"]) for r in file_records]

    if not code_files:
        return "⛔ All files are duplicates."

    batch_size = 3
    batch_count = ceil(len(code_files) / batch_size)

    for chunk in chunk_list(code_files, batch_size):
        core.execute_batch_process(chunk, project)

    msg = f"✅ Uploaded {len(code_files)} new files. Created {batch_count} Batch Groups."

    if skipped_files:
        msg += f"\n⛔ Skipped {len(skipped_files)} duplicate files: {', '.join(skipped_files)}"

    return msg

# --------------------------
# [2] 상태 보기 (Meta + DB)
# --------------------------

def get_batch_status():

    core.status_update()
    meta_status = core.get_status()
    rows = []
    # Meta status
    for meta in meta_status:
        rows.append({
            "project": meta.get("project"),
            "page_type": meta.get("page_type"),
            "Status": meta.get("status"),
            "last_updated_at": meta.get("last_updated_at"),
            "batch_id": meta.get("batch_id")
        })

    return pd.DataFrame(rows)

# --------------------------
# [3] 다운로드 가능한 메타 파일
# --------------------------

def get_downloadable_files():
    metas = core.get_status()
    core.postprocess_results()
    downloadable = {}
    files = os.listdir(os.path.join(config.RESULT_DIR, "output"))
    for file in files:
        if file.endswith(".csv"):
            downloadable[file] = os.path.join(config.RESULT_DIR,"output", file)

    return downloadable

def download_file(file_path):
    return file_path

def download_selected_files_as_zip(selected_files):
    all_files = get_downloadable_files()
    temp_dir = tempfile.mkdtemp()

    for fname in selected_files:
        if fname in all_files:
            shutil.copy(all_files[fname], os.path.join(temp_dir, fname))

    zip_path = shutil.make_archive(os.path.join(temp_dir, "batch_results"), 'zip', temp_dir)
    return zip_path
# --------------------------
# Gradio UI
# --------------------------

with gr.Blocks() as demo:
    gr.Markdown("# 📦 Batch Processor (Meta + DB 동시 관리 최종)")

    with gr.Tab("📄 Upload PDF → Batch"):
        upload_input = gr.File(label="Upload PDF Files", file_types=[".pdf"], file_count="multiple")
        project_input = gr.Textbox(label="Project Name", placeholder="Enter project name")
        upload_button = gr.Button("Upload and Submit Batch")
        upload_output = gr.Textbox(label="Upload Result", lines=5)
        remove_temp_button = gr.Button("Remove Temp Files")
        remove_temp_output = gr.Textbox(label="Temp Files Status", lines=1)

        remove_temp_button.click(
            clean_temp_dir, inputs = [], outputs=[remove_temp_output]
        )
        upload_button.click(upload_files_and_batch, inputs=[upload_input,project_input], outputs=[upload_output])

    with gr.Tab("📊 View Status (Meta + DB"):
        status_button = gr.Button("Update & View Status")
        status_output = gr.Dataframe(label="Current Meta + DB Status", interactive=False)

        status_button.click(get_batch_status, outputs=[status_output])

    with gr.Tab("⬇️ Download Batch Results (Meta)"):
        file_selector = gr.CheckboxGroup(label="Select files to include", choices=[])
        refresh_button = gr.Button("Refresh Downloadable Files")
        download_button = gr.Button("Download Selected as ZIP")
        run_postprocess_button = gr.Button("📄 Run Postprocess")
        download_file_output = gr.File(label="Download ZIP")
        postprocess_output = gr.Textbox(label="Postprocess Status")

        refresh_button.click(
            lambda: gr.update(choices=list(get_downloadable_files().keys())),
            outputs=[file_selector]
        )

        download_button.click(
            download_selected_files_as_zip,
            inputs=[file_selector],
            outputs=[download_file_output]
        )

        run_postprocess_button.click(
            lambda: (core.postprocess_results() or "✅ Postprocess completed."),
            outputs=[postprocess_output]
        )

demo.launch(server_name="0.0.0.0", server_port=7860, ssl_keyfile=None, ssl_certfile=None)
