import os
import json
import pandas as pd
import numpy as np
from json_repair import repair_json
from config.config import FORMAT_VALIDATION_TEMPLATE, MUST_INCLUDE, FINAL_DF_FORMAT, PAGE_MAP, DATE_MAPPER
from IOmanager.meta_manager import MetaManager

class PostProcessor:
    def __init__(self, batch_meta_path, file_code_path, result_root, output_dir, meta_path):
        self.batch_meta_path = batch_meta_path
        self.file_code_path = file_code_path
        self.result_root = result_root
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.meta_manager = MetaManager(meta_path)
        self.must_include = ['임가번호', '날', '짜']

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

    @staticmethod
    def check_numeric(value):
        try:
            float(value)
            return True
        except:
            return False

    def load_meta(self):
        with open(self.batch_meta_path, 'r', encoding='utf-8') as f:
            batch_records = [json.loads(line) for line in f if '"status": "completed"' in line]

        with open(self.file_code_path, 'r', encoding='utf-8') as f:
            file_code_map = {j['org_filename']: j['code_filename'] for j in map(json.loads, f)}

        meta = []
        for batch in batch_records:
            for org_file in batch['original_file_ids']:
                code_file = file_code_map.get(org_file)
                if code_file:
                    meta.append({
                        "group_id": batch["group_id"],
                        "project_name": batch["project"],
                        "batch_id": batch["batch_id"],
                        "org_filename": org_file,
                        "file_id": code_file.split('.')[0],
                        "id_code": org_file.split('.')[0]
                    })

        df = pd.DataFrame(meta)
        jsonl_paths = df.drop_duplicates().apply(
            lambda x: os.path.join(self.result_root, f"{x['project_name']}_{x['batch_id']}_response.jsonl"), axis=1).tolist()

        return jsonl_paths, df[["file_id", "id_code"]].drop_duplicates()

    def filter_spending_type(self, value, remove_text):
        if ":" in value:
            parts = value.split(":")
            if len(parts) > 1 and parts[1] in remove_text:
                return parts[0]
        for text in remove_text:
            if text in value:
                value = value.replace(text, "")
        return value

    def process_table(self, df, table_name):
        temp_df = df[df["table_name"] == table_name].copy()
        format_table = pd.DataFrame(columns=FINAL_DF_FORMAT[table_name]["coiumns"])
        temp_df = pd.concat([format_table, temp_df], ignore_index=True)

        if "수입" in table_name:
            temp_df['유형'] = "1"
        if "지출" in table_name:
            temp_df['유형'] = "2"

        if table_name == "수입":
            remove_text = ['외', '상', '판', '매', '외상', '판매', '외상판매']
            temp_df['수입의 종류'] = temp_df['수입의 종류'].apply(lambda x: self.filter_spending_type(x, remove_text))

        if table_name == "지출":
            remove_text = ['외', '상', '카', '드', '구', '입', '상도', '외카', '상드', '구구', '입입', '임임', '입임', '임입']
            temp_df['지출의 종류'] = temp_df['지출의 종류'].apply(lambda x: self.filter_spending_type(x, remove_text))

        if "자가농업 생산물 중 자가소비량" in table_name:
            mapper = {"20": "1", "30": "2", "40": "3", "52": "4"}
            temp_df['차수'] = temp_df['page'].map(mapper)
            temp_df['지출'] = "81012"

        if temp_df.columns.str.contains("수입").any():
            temp_df['수입'] = temp_df['수입'].apply(lambda x: x[:5] if len(x) > 5 else x)
            temp_df['지출'] = temp_df['지출'].apply(lambda x: x[-5:] if len(x) > 5 else x)

        if table_name in ["수입", "지출", "임업노동 투입내역", "동력사용시간", "자가임업생산물 중 자가소비량"]:
            temp_df['page'] = temp_df['page'].astype(str)
            temp_df[['날', '짜']] = temp_df['page'].map(DATE_MAPPER).apply(pd.Series)

        string_cols_to_check = ['재배형태', '수입의 종류', '수입원',
                                '지출의 종류', '용도',
                                '재배형태작업명', '명칭', '생산물', '생산물 상세']
        actual_cols = temp_df.columns[temp_df.columns.isin(string_cols_to_check)]

        for col in actual_cols:
            temp_df[col] = temp_df[col].apply(lambda x: x if not self.check_numeric(x) else '')

        drop_cols = [col for col in temp_df.columns if col not in FINAL_DF_FORMAT[table_name]["coiumns"]]
        temp_df.drop(columns=drop_cols, inplace=True, errors="ignore")

        temp_df.columns = FINAL_DF_FORMAT[table_name]["rename"]
        return temp_df.drop_duplicates()

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        jsonl_paths, info_df = self.load_meta()

        for jsonl_path in jsonl_paths:
            project_name, batch_id = os.path.basename(jsonl_path).split("_")[:2]
            month = batch_id
            df = pd.DataFrame()

            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    outer = json.loads(line)
                    file_id = outer['custom_id']
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

                    page_table = PAGE_MAP.get(file_id.split("_")[1], [])
                    for table_name in page_table:
                        flattened = []
                        table_data = next((entry['table_data'] for entry in content_raw if entry['table_name'] == table_name), [])
                        if table_data == []:
                            flattened.append({
                                "file_id": file_id.split("_")[0],
                                "page": file_id.split("_")[1],
                                "table_name": table_name
                            })
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
                        if not temp.empty:
                            df = pd.concat([df, temp], ignore_index=True)

            if df.empty:
                continue

            df = pd.merge(df, info_df, on='file_id', how='left')
            df['임가번호'] = df['id_code']
            df.fillna('', inplace=True)
            final_df = df.copy()

            table_names = final_df['table_name'].unique()
            for table_name in table_names:
                temp_df = self.process_table(final_df, table_name)

                output_name = "수입(지출).csv" if table_name in ['수입', '지출'] else f"{table_name}.csv"
                project_name_month = f"{project_name}_{month}"
                output_name = f"{project_name_month}_{output_name}"
                output_dir_update = os.path.join(self.output_dir, project_name_month)
                os.makedirs(output_dir_update, exist_ok=True)
                output_path = os.path.join(output_dir_update, output_name)

                temp_df.to_csv(output_path, index=False, encoding='utf-8-sig', mode='a', header=not os.path.exists(output_path))

            os.remove(jsonl_path)

            csv_files = [f for f in os.listdir(output_dir_update) if f.endswith('.csv')]
            excel_output_path = os.path.join(self.output_dir, f"{project_name}_output.xlsx")
            with pd.ExcelWriter(excel_output_path, engine='xlsxwriter') as writer:
                for csv_file in csv_files:
                    df = pd.read_csv(os.path.join(output_dir_update, csv_file))
                    df = df.drop_duplicates()
                    sheet_name = os.path.basename(csv_file).split('.')[0].split('_')[-1]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
