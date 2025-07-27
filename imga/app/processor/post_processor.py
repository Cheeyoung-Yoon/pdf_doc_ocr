
import os
import json
import pandas as pd
import numpy as np
import shutil
from multiprocessing import Pool, cpu_count
from json_repair import repair_json
from config.config import FORMAT_VALIDATION_TEMPLATE, MUST_INCLUDE, FINAL_DF_FORMAT, PAGE_MAP, DATE_MAPPER, META_DIR, RESULT_DIR, PDF_DIR, IMAGE_DIR
from IOmanager.meta_manager import MetaManager
from collections import defaultdict
import re

class PostProcessor:
    print("PostProcessor initialized with paths:")
    def __init__(self, batch_meta_path, file_code_path, result_root, output_dir, meta_path):
        self.batch_meta_path = batch_meta_path
        self.file_code_path = file_code_path
        self.result_root = result_root
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.meta_manager = MetaManager(meta_path)

    def safe_get(self, value):
        if isinstance(value, list):
            return value[0] if value else ""
        return value

    def flatten_dict(self, d, parent_key="", sep="_", depth=0, max_depth=5):
        items = {}
        if depth > max_depth:
            return items
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(self.flatten_dict(v, new_key, sep, depth + 1, max_depth))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                items.update(self.flatten_dict(v[0], new_key, sep, depth + 1, max_depth))
            else:
                items[new_key] = self.safe_get(v)
        return items
    
    @staticmethod
    def check_numeric(value):
        try:
            float(value)
            return True
        except:
            return False
        
        
    @staticmethod
    def detect_nulls(df):
        cols = df.columns
        must_include_adj = [col for col in MUST_INCLUDE if col in cols]
        cols = [col for col in df.columns if col not in MUST_INCLUDE]
        df[cols] = df[cols].where(df[cols] != '', np.nan)
        to_drop = df[cols].isna().all(axis=1)
        
        group = df.groupby(must_include_adj)
        keep_first = group == 0
        final_mask = ~(to_drop & ~keep_first)
        r_df = df[final_mask].reset_index()
        
        return r_df
    
    
    def load_meta(self):
        with open(self.batch_meta_path, "r", encoding="utf-8") as f:
            batch_records = [json.loads(line) for line in f if '"status": "completed"' in line]

        with open(self.file_code_path, "r", encoding="utf-8") as f:
            file_code_map = {j["org_filename"]: j["code_filename"] for j in map(json.loads, f)}

        meta = []
        for batch in batch_records:
            for org_file in batch["original_file_ids"]:
                code_file = file_code_map.get(org_file)
                if code_file:
                    meta.append({
                        "group_id": batch["group_id"],
                        "project_name": batch["project"],
                        "batch_id": batch["batch_id"],
                        "org_filename": org_file,
                        "file_id": code_file.split(".")[0],
                        "id_code": org_file.split(".")[0],
                    })

        df = pd.DataFrame(meta)
        jsonl_paths = df.drop_duplicates().apply(
            lambda x: os.path.join(self.result_root, f"{x["project_name"]}_{x["batch_id"]}_response.jsonl"), axis=1
        ).tolist()
        return jsonl_paths, df[["file_id", "id_code"]].drop_duplicates()
    
    
    @staticmethod
    def safe_get(value):
        if isinstance(value, list):
            return value[0] if value else ''
        return value
    
    
    def flatten_dict(self, d, parent_key='', sep='_', depth=0, max_depth=5):
        items = {}
        if depth > max_depth:
            return items
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(self.flatten_dict(v, new_key, sep, depth + 1, max_depth))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                items.update(self.flatten_dict(v[0], new_key, sep, depth + 1, max_depth))
            else:
                items[new_key] = self.safe_get(v)
        return items




    def parse_jsonl_file(self, args):
        jsonl_path, info_df, output_root = args
        normalized_path = os.path.normpath(jsonl_path)


        if not os.path.exists(jsonl_path):
            print(f"File not found: {jsonl_path}")

        batch_id = os.path.basename(jsonl_path).split("_")[-2]
        project_name = os.path.basename(jsonl_path).split("_")[0]
        month = os.path.basename(jsonl_path).split("_")[1]
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            df = pd.DataFrame()
            for line in f:
                outer = json.loads(line)
                file_id = outer['custom_id']
                # file_id = custom_id.split("_")[0]
                # page = custom_id.split("_")[1]
                content = outer["response"]["body"]["choices"][0]["message"]["content"]
                try:
                    content_raw = json.loads(content)
                except:
                    try:
                        content_raw = content.split("```json")[1].split("```")[0]
                        content_raw = json.loads(content_raw)
                    except:
                        try:
                            content_raw = repair_json(content)
                            content_raw = json.loads(content_raw)
                        except:
                            print(f"Error parsing JSON for file_id {file_id}: {content}")
                            continue

                if not isinstance(content_raw, list):
                    content_raw = [content_raw]
                if content_raw == ['']:
                    content_raw = []
                page_table = PAGE_MAP.get(file_id.split("_")[1], "")
                # loop_table = [table['table_name'] for table in content_raw if 'table_name' in table]
                for table_name in page_table:
                    flattened = []
                    
                    table_data = next(
                                (entry['table_data'] for entry in content_raw if entry['table_name'] == table_name),
                                [])
                        
                    
                    if table_data == []:
                    
                        flat_row = {
                            "file_id": file_id.split("_")[0],
                            "page": file_id.split("_")[1],
                            "table_name": table_name
                        }
                        flattened.append(flat_row) 
                    else:
                        
                        for row in table_data:
                            
                            flat_row = {
                                "file_id": file_id.split("_")[0],
                                "page": file_id.split("_")[1],
                                "table_name": table_name
                            }
                            
                            flat_row.update(self.flatten_dict(row))
                            
                            valid_format = FORMAT_VALIDATION_TEMPLATE.get(table_name, {})
                            for key in valid_format.keys():
                                if key not in flat_row:
                                    flat_row[key] = ""
                            flattened.append(flat_row)   

                    temp = pd.DataFrame(flattened)

                    if temp.empty:
                        continue
                    df = pd.concat([df, temp], ignore_index=True)

            if df.empty:
                pass
            df = pd.merge(df, info_df, on='file_id', how='left')
            df['임가번호'] = df['id_code']

            # df = detect_nulls(df)
            df.fillna('', inplace=True)
            final_df= df.copy()
            
            table_names = final_df['table_name'].unique()
            # final_df['table_name'] = final_df['table_name'].str.replace("자가임업생산물 중 자가소비량", "자가농업 생산물 중 자가소비량")
            def filter_spending_type(value, remove_text):
                # Split the string by ":" if present
                if ":" in value:
                    parts = value.split(":")
                    
                    if len(parts) > 1 and parts[1] in remove_text:
                        return parts[0]
                else:
                    for text in remove_text:
                        remove = [remove_part for remove_part in remove_text if remove_part in value]
                        if len(remove) > 0:
                            # Remove the text from the string
                            remove = remove[0]
                            value = value.replace(remove, "")
                    return value
                
            
            for table_name in table_names:
        # table_name = "수입"
                # if "자가농업 생산물 중 자가소비량" in table_name:
                #     table_name = "자가농업 생산물 중 자가소비량"
                try:
                    df = final_df[ final_df["table_name"] == table_name]
                    if len(df) == 0:
                        raise ValueError(f"No data found for table: {table_name}")
                except ValueError as e:
                        df = final_df[ final_df["table_name"].str.contains(table_name, na=False)]

                format_table = pd.DataFrame(columns = FINAL_DF_FORMAT[table_name]["coiumns"])
                
                temp_df = pd.concat([format_table, df], ignore_index=True)

                
                if "수입" in table_name:
                    temp_df['유형'] = "1"

                if "지출" in table_name:
                    temp_df['유형'] = "2"
                
                if table_name == "수입":
                    remove_text = ['외','상','판','매','외상','판매','외상판매']

                    ##### 여기 로직 확인이 필요함
                    # 재배형태가 null 임에 따라서 밀림 현상 발견견
                    # temp_df['수입원'] = temp_df.apply(lambda x: x['수입원']  if check_numeric(x['재배형태']) else x['수입의 종류'], axis=1)
                    # temp_df['수입의 종류'] = temp_df.apply(lambda x: x['수입의 종류']  if check_numeric(x['재배형태']) else x['재배형태'], axis=1)
                    # temp_df['재배형태'] = temp_df.apply(lambda x: x['재배형태'] if check_numeric(x['재배형태']) else '' , axis=1)
                    temp_df['수입의 종류'] = temp_df['수입의 종류'].apply(lambda x: filter_spending_type(x, remove_text))

                if table_name == "지출":
                    remove_text = ['외','상','카','드','구','입','상도','외카','상드','구구','입입','임임','입임','임입']

                    temp_df['지출의 종류'] = temp_df['지출의 종류'].apply(lambda x: filter_spending_type(x, remove_text))

                if "자가농업 생산물 중 자가소비량" in table_name:
                    mapper = {"20": "1", "30": "2", "40": "3", "52": "4"}
                    temp_df['차수'] = temp_df['page'].map(mapper)
                    temp_df['지출'] = "81012"

                if temp_df.columns.str.contains("수입").any():
                    temp_df['수입'] = temp_df['수입'].apply(lambda x: x[:5] if len(x) > 5 else x)
                    temp_df['지출'] = temp_df['지출'].apply(lambda x: x[-5:] if len(x) > 5 else x)
                    
                if table_name in ["수입","지출","임업노동 투입내역","동력사용시간","자가임업생산물 중 자가소비량"]:

                    temp_df['page'] = temp_df['page'].astype(str)
                    temp_df[['날', '짜']] = temp_df['page'].map(DATE_MAPPER).apply(pd.Series)


                string_cols_to_check = ['재배형태','수입의 종류','수입원',
                                        '지출의 종류','용도',
                                        '재배형태''작업명','명칭','생산물','생산물 상세']
                
                actual_cols = temp_df.columns[temp_df.columns.isin(string_cols_to_check)]
                

                for col in actual_cols:
                    temp_df[col] = temp_df[col].apply(lambda x: x if not self.check_numeric(x) else '')
                
                drop_cols = [col for col in temp_df.columns if col not in FINAL_DF_FORMAT[table_name]["coiumns"]]
                temp_df.drop(columns=drop_cols, inplace=True, errors="ignore")

                # cleaned = detect_nulls(temp_df)
                cleaned = temp_df.copy()
    
                cleaned = cleaned[FINAL_DF_FORMAT[table_name]["coiumns"]]

                
                cleaned.columns = FINAL_DF_FORMAT[table_name]["rename"]

                if table_name in ["자동이체_수입", "자동이체_지출"]:
                    output_name = f"자동이제_수입(지출)_{batch_id}.csv"
                elif table_name in ['수입','지출']:
                    output_name = f"수입(지출)_{batch_id}.csv"
                else:       
                    output_name = f"{table_name}_{batch_id}.csv"
                print(f"Processing table: {output_name}")
                    
                    
                project_name_month = project_name + "_" + month 
                # output_name = os.path.join(project_name_month, output_name)
                output_dir_update= os.path.join(self.output_dir, project_name_month, "temp_results")
                os.makedirs(output_dir_update, exist_ok=True)
                output_path = os.path.join(output_dir_update, output_name)
                cleaned = cleaned.drop_duplicates()
                cleaned.to_csv(output_path, index=False, encoding='utf-8-sig', mode='w')
                print(f"Processed {output_path} for {project_name_month}")

    def combine_to_excel(self, project_name):
        project_dir = os.path.join(self.output_dir, project_name, "temp_results")
        excel_path = os.path.join(self.output_dir, "..",'..',"result", f"{project_name}_output.xlsx")
        excel_path = os.path.abspath(excel_path) 
        print(f"Combining results for project: {project_name} into {excel_path}")
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)

        # 테이블명별로 파일 그룹화
        table_files = defaultdict(list)
        for fname in os.listdir(project_dir):
            if fname.endswith(".csv") and "_" in fname:
                table_name = fname.split("_")[0]
                table_files[table_name].append(os.path.join(project_dir, fname))

        with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
            for table_name, file_paths in table_files.items():
                dfs = [pd.read_csv(path) for path in file_paths]
                if dfs:
                    df_merged = pd.concat(dfs, ignore_index=True).drop_duplicates()
                    df_merged.to_excel(writer, sheet_name=table_name[:31], index=False)

        shutil.rmtree(os.path.join(self.output_dir, project_name, "temp_results"))


    def remove_temp_files(self, jsonl_paths):
        temp_dir = os.path.join(self.output_dir, "temp_results")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Removed temporary files from {temp_dir}")
        else:
            print(f"No temporary files found at {temp_dir}")
            
        batch_ids = set()
        for path in jsonl_paths:
            match = re.search(r"_(batch_[a-f0-9]+)_response\.jsonl$", os.path.basename(path))
            if match:
                batch_ids.add(match.group(1))

        # 상태 업데이트
        for batch_id in batch_ids:
            self.meta_manager.upsert_batch_meta(
                batch_id=batch_id,
                status="finish",
            )
        if os.path.exists(IMAGE_DIR):
            shutil.rmtree(IMAGE_DIR)
            print(f"Removed image directory: {IMAGE_DIR}")
            os.makedirs(IMAGE_DIR, exist_ok=True)
        if os.path.exists(PDF_DIR):
            shutil.rmtree(PDF_DIR)
            print(f"Removed PDF directory: {PDF_DIR}")
            os.makedirs(PDF_DIR, exist_ok=True) 
        if os.path.exists(RESULT_DIR):
            shutil.rmtree(RESULT_DIR)
            print(f"Removed meta directory: {RESULT_DIR}")
            os.makedirs(RESULT_DIR, exist_ok=True)



    def run(self):
        print("Post-processing started...")
        print("the root path is", os.getcwd())
        jsonl_paths, info_df = self.load_meta()
        print(f"Found {len(jsonl_paths)} JSONL files to process.")
        grouped_args = [(path, info_df, self.output_dir) for path in jsonl_paths]

        with Pool(processes=min(cpu_count(), 8)) as pool:
            pool.map(self.parse_jsonl_file, grouped_args)
            pool.close()
            pool.join()
        print("multiprocess done")
        project_names = list(set([
                "_".join(os.path.basename(p).split("_", maxsplit=2)[:2])
                for p in jsonl_paths]))
        for project in project_names:
            self.combine_to_excel(project)
        print("Post-processing completed. Results saved to Excel files.")
        self.remove_temp_files(jsonl_paths)
        print("Temporary files removed and final outputs cleaned up.")