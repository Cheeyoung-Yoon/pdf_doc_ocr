from processor.post_processor import PostProcessor
from multiprocessing import freeze_support
import os
if __name__ == "__main__":
    processor = PostProcessor(
        batch_meta_path="./data/meta_info/batch_meta.jsonl",
        file_code_path="./data/meta_info/file_codes.json",
        result_root="./data/batch_results",
        output_dir="./final_outputs",
        meta_path="./data/meta_info"
    )
    print("the root path is", os.getcwd())
    print("Starting post-processing...")
    freeze_support()
    processor.run()
