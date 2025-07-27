import os
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 

PDF_DIR = r".\data\temp_work_dir\raw"
IMAGE_DIR = r".\data\temp_work_dir\pre_processed"
RESULT_DIR = "./data/batch_results"
META_DIR = r".\data\meta_info"
PAGE_TYPE_MAPPING = {
    "exclude": [8, 21, 31, 41, 53],
    "임산물 현황": [9],
    "은행 자동이체 수입": [10],
    "은행 자동이체 지출": [11],
    "수입": [12, 14, 16, 18, 22, 24, 26, 28, 32, 34, 36, 38, 42, 44, 46, 48, 50],
    "지출": [13, 15, 17, 19, 23, 25, 27, 29, 33, 35, 37, 39, 43, 45, 47, 49, 51],
    "자가농업 소비": [20, 30, 40, 52]
}

PROMPT_MAPPING = {
    "임산물 현황": """
   You will be provided part of scanned file that is splited in to 3 containing a single table titled "임산물 현황".

Extract all data from the table strictly according to the following rules and return the result in this **exact JSON format**:

### JSON Format
{
  "table_name": "임산물 현황",
  "table_data": [
    {
      "지번": [""],                     // dtype: string
      "지목": [""],                     // dtype: string
      "읍면동": [""],                   // dtype: string
      "가능면적(평)": [""],             // dtype: string (numeric string)
      "재배 작물명": [""],              // dtype: string
      "작물 부호": [""],                // dtype: string or numeric code
      "면적": [""],                     // dtype: string (numeric string)
      "주생산물 수확량": [""],           // dtype: string (numeric string)
      "주생산물 수확량 단위": [""],       // dtype: string
      "주생산물 판매량": [""],           // dtype: string (numeric string)
      "주생산물 판매량 단위": [""],       // dtype: string
      "부생산물 수확량": [""],           // dtype: string (numeric string)
      "부생산물 수확량 단위": [""],       // dtype: string
      "부생산물 판매량": [""],           // dtype: string (numeric string)
      "부생산물 판매량 단위": [""]        // dtype: string
    }
  ]
}

⚠️ Note:
- The **dictionary keys must strictly follow the column order** as shown in the actual table layout. Do not reorder or rename.
- Each value must be returned as a **list of strings**, even if there's only one value.
- Do not infer meaning or guess column identity. Use the **column position only** to assign values.
- You must strictly follow the table's physical structure for cell positions and column alignment.

### Extraction Rules
- Extract all rows while maintaining accurate column alignment.
- Column position takes precedence over content. Never reassign fields based on context or semantics.
- If handwriting crosses cell boundaries, infer the intended column using semantic context and row structure.
- If any cell is empty, return [""] in that column.
- Ditto marks (" ", `"`, `―`) → Replace with the valid value above in the same column.
- Crossed-out values → Replace with nearest valid edited value in row or column.
- Handwritten numbers:
  - Remove non-decimal dots (e.g. `1.0.2` → `102`)
  - Horizontal line (`―`) → append `000` (e.g. `12,―` → `12000`)
- Invalid Korean text from OCR → Do not correct; leave as-is.
- Return only the full, valid JSON structure. No explanations or free text.
- if duplicate rows are found, remove them and keep only one.

Do not generate multiple empty rows unless there are clearly duplicated actual rows that must be preserved.
"""
    ,
    "은행 자동이체 수입": """
    You will be provided part of scanned file that is splited in to 3 containing a single table titled "자동이체_수입".  
Extract data from the table according to the extraction rules and return the result in the following JSON format.

### JSON Format

{
    "table_name": "자동이체_수입",
    "table_data": [
        {
            "수입": [""],         # dtype: string (5-digit numeric string)
            "지출": [""],         # dtype: string (5-digit numeric string)
            "재배형태": [""],     # dtype: string (2-digit numeric string)
            "수입의 종류": [""],   # dtype: string (Korean text)
            "수입원": [""],       # dtype: string (Korean text)
            "수량": [""],         # dtype: string (numeric or Korean text)
            "단위": [""],         # dtype: string (Korean unit label)
            "현금": [""]          # dtype: string (amount in numeric string)
        }
    ]
}

⚠️ Notes:
- The dictionary keys must strictly follow the column order as shown in the table layout. Do not reorder or rename any keys.
- Each value must be returned as a **list of strings**, even if there's only one value.
- Do not infer meaning or change fields based on context. Use column **position only** to decide which field a value belongs to.

### Extraction Rules

- Extract all rows **while maintaining accurate column alignment**.
- You must place each value in the correct field **based on column structure**, not based on value type or context.
- All cell breaks are based on column grid; do not split by sub-cell content.
- For "수입" and "지출" columns:
    → These are 5-digit numeric fields with vertical bars (e.g. |1|2|3|4|5|)  
    → Ignore the bars and return the result as a numeric string (e.g. "12345")
- If handwriting crosses cell boundaries, infer the correct column based on overall row layout and structure.
- If a cell is empty, return `[""]` in that column.
- Ditto marks (" ", `"`, `―`) → Replace with the nearest valid value above in the same column.
- Crossed-out values → Replace with the nearest edited value in the same row or column.
- Handwritten numbers:
    - Remove non-decimal dots (e.g. `1.0.2` → `102`)
    - Horizontal line (`―`) → Append `000` (e.g. `12,―` → `12000`)
- For invalid OCR Korean text → Do not correct; return as-is.
- Return only valid full JSON structure. No explanations or free text.
- if duplicate rows are found, remove them and keep only one.
Do not generate multiple empty rows unless there are clearly duplicated actual rows that must be preserved.
    """,
    
    "은행 자동이체 지출": """
    You will be provided part of scanned file that is splited in to 3  containing a single table titled "자동이체_지출".  
Extract data from the table according to the extraction rules and return the result in the following JSON format.

### JSON Format

{
    "table_name": "자동이체_지출",
    "table_data": [
        {
            "수입": [""],         # dtype: string (5-digit numeric string)
            "지출": [""],         # dtype: string (5-digit numeric string)
            "지출의 종류": [""],   # dtype: string (Korean text)
            "용도": [""],         # dtype: string (Korean text)
            "수량": [""],         # dtype: string (numeric or text)
            "단위": [""],         # dtype: string (Korean unit label)
            "현금": [""]          # dtype: string (amount in numeric string)
        }
    ]
}

⚠️ Notes:
- The dictionary keys must strictly follow the **column order** of the table. Do not change the order.
- Each value must be returned as a **list of strings**, even if it contains only one value.
- Do not infer or reassign fields based on context, value type, or meaning. **Use only the column position**.

### Extraction Rules

- Extract all rows **while maintaining accurate column alignment**.
- You must place the value in the correct field based **only on table structure position**.
- Do not guess the column based on value type or content.
- All cell breaks follow **column boundaries**, not sub-cells.
- For "수입" and "지출":
    - These are 5-digit numeric fields formatted with vertical bars (e.g., |1|2|3|4|5|).
    - Return them as a stringified number (e.g., "12345") by removing the bars.
- If handwriting crosses column borders, infer the correct column based on row structure.
- If any cell is empty, return `[""]` for that column.
- Ditto marks (" ", `"`, `―`) → Replace with the **nearest valid value above** in the same column.
- Crossed-out values → Replace with the **nearest valid edited value** in the same row or column.
- Handwritten numbers:
    - Remove non-decimal dots (e.g., `1.0.2` → `102`)
    - Horizontal line (`―`) → Append `000` (e.g., `12,―` → `12000`)
- If OCR misreads Korean text → Do **not** correct it; use as-is.
- Return only the valid full JSON structure. **No explanations or free text**.
Do not generate multiple empty rows unless there are clearly duplicated actual rows that must be preserved.
- if duplicate rows are found, remove them and keep only one.
    """,
    
    "수입": """
   You will be provided part of scanned file that is splited in to 3  that contains two tables and handwritten Korean text and numbers.  
Extract data from the tables according to the extraction rules and return the result in the following JSON format.

Each table must be extracted separately using its title as `table_name`.

### Table Names
- 수입
- 임업노동 투입내역

### JSON Format

[
  {
    "table_name": "수입",
    "table_data": [
        {
            "수입": [""],                    # dtype: string (5-digit numeric string)
            "지출": [""],                    # dtype: string (5-digit numeric string)
            "재배형태": [""],                # dtype: string (2-digit numeric string)
            "수입의 종류": [""],              # dtype: string (Korean text, last 3 rows include 외상판매 prefix)
            "수입원": [""],                  # dtype: string (Korean text)
            "수량": [""],                    # dtype: string (numeric or Korean text)
            "단위": [""],                    # dtype: string (Korean unit)
            "현금(원)": [""],                # dtype: string (numeric string)
            "현물(평가액)": [""]              # dtype: string (numeric string)
        }
    ]
  },
  {
    "table_name": "임업노동 투입내역",
    "table_data": [
        {
            "품목명": [""],                  # dtype: string
            "품목 부호": [""],               # dtype: (3-digit numeric string)
            "작업명": [""],                  # dtype: string
            "작업 부호": [""],               # dtype: (2-digit numeric string)
            "작업면적": [""],                # dtype: string (numeric)
            "수확량": [""],                  # dtype: string (numeric)
            "단위": [""],                    # dtype: string (unit)
            "노동투입시간 경영주": [""],     # dtype: string (numeric)
            "노동투입시간 배우자": [""],     # dtype: string (numeric)
            "가족노동 남": [""],             # dtype: string (numeric)
            "가족노동 여": [""],             # dtype: string (numeric)
            "고용노동 남": [""],             # dtype: string (numeric)
            "고용노동 여": [""],             # dtype: string (numeric)
            "품앗이 남": [""],               # dtype: string (numeric)
            "품앗이 여": [""],               # dtype: string (numeric)
            "일손돕기 남": [""],             # dtype: string (numeric)
            "일손돕기 여": [""]              # dtype: string (numeric)
        }
    ]
  }
]

⚠️ Notes:
- The **dictionary keys must strictly follow the column order** as shown in each table's layout. Do not reorder or rename.
- Every value must be returned as a **list of strings**, even if the cell contains only one value.
- Do not infer or reassign fields based on context, value type, or content. **Use only the column position**.

### Extraction Rules

- Extract all rows **while maintaining accurate column alignment**.
- Assign values strictly based on **visual column structure**, not contextual meaning.
- All cell breaks occur based on column boundaries, not text content.
- For "수입" and "지출" columns:
  - Always determine based on visual layout. Do **not** infer based on numeric format.
  - The left column is always "수입", right is "지출".
  - These are 5-digit numeric fields with vertical bars (e.g., |1|2|3|4|5|). Remove bars and return as a stringified number (e.g., "12345").
- If handwriting crosses cell boundaries, infer the intended column based on **row structure** and alignment.
- If any cell is empty, return `[""]` for that field.
- Ditto marks (" ", `"`, `―`) → Replace with valid value **above** in the same column.
- Crossed-out values → Replace with the **nearest valid edited value** in the same row or column.
- Handwritten numbers:
  - Remove non-decimal dots (e.g., `1.0.2` → `102`)
  - Replace horizontal line (`―`) with `000` (e.g., `12―` → `12000`)
- For invalid OCR-recognized Korean → **Do not fix or interpret**; return as-is.
- if duplicate rows are found, remove them and keep only one.
- Return only the full, valid JSON structure. No explanations or free text.
### Special Rule

- only in "수입의 종류" column has a last 3 rows with side label `"외상판매"`:
  → Combine it as a prefix:  
  e.g., `외상판매: 수입종류값`

### Final Rule


Do not generate multiple empty rows unless there are clearly duplicated actual rows that must be preserved.
- Output must be valid JSON only. **Do not include any extra text, explanations, or logs**.
    """,
    
    "지출": """
you are a data extraction expert. So no need to be creative, strictly follow the instructions and extract the data as per the instructions.
Extract data from the table accoring to the extration rules and return the result in the following JSON format.
part of scanned file that is splited in to 3.
### Tables to Extract
Extract each table **separately** using its **title** as `"table_name"`:
- `지출`
- `동력사용시간`
- `자가임업생산물 중 자가소비량`

### Output Format (JSON)
Return the result as a JSON list of tables, with the following schema:


[
  {
    "table_name": "지출",
    "table_data": [
      {
        "수입": [""],               # dtype: string (5-digit numeric string)
        "지출": [""],               # dtype: string (5-digit numeric string)
        "지출의 종류": [""],         # dtype: string (text, may include 외상/카드 prefix)
        "용도": [""],               # dtype: string
        "수량": [""],               # dtype: string
        "단위": [""],               # dtype: string
        "현금(원)": [""],           # dtype: string (numeric string)
        "현물(평가액)": [""]         # dtype: string (numeric string)
      }
    ]
  },
  {
    "table_name": "동력사용시간",
    "table_data": [
      {
        "명칭": [""],               # dtype: string
        "부호": [""],               # dtype: string (5-digit numeric string)
        "자가 시간": [""],          # dtype: string (numeric)
        "임차 시간": [""]           # dtype: string (numeric)
      }
    ]
  },
  {
    "table_name": "자가임업생산물 중 자가소비량",
    "table_data": [
      {
        "수입": [""],               # dtype: string (5-digit numeric string)
        "지출": [""],               # dtype: string (5-digit numeric string)
        "생산물": [""],             # dtype: string
        "용도": [""],               # dtype: string
        "수량": [""],               # dtype: string
        "단위": [""],               # dtype: string
        "현물평가액": [""]          # dtype: string (numeric string)
      }
    ]
  }
]
⚠️ Notes:
- The **dictionary keys must strictly follow the column order** as shown in each table's layout. Do not reorder or rename.
- Every value must be returned as a **list of strings**, even if the cell contains only one value.
- Do not infer or reassign fields based on context, value type, or content. **Use only the column position**.

### Extraction Rules

- Extract all rows **while maintaining accurate column alignment**.
- Assign values strictly based on **visual column structure**, not contextual meaning.
- All cell breaks occur based on column boundaries, not text content.
- For "수입" and "지출" columns:
  - Always determine based on visual layout. Do **not** infer based on numeric format.
  - The left column is always "수입", right is "지출".
  - These are 5-digit numeric fields with vertical bars (e.g., |1|2|3|4|5|). Remove bars and return as a stringified number (e.g., "12345").
- If handwriting crosses cell boundaries, infer the intended column based on **row structure** and alignment.
- If any cell is empty, return `[""]` for that field.
- Ditto marks (" ", `"`, `―`) → Replace with valid value **above** in the same column.
- Crossed-out values → Replace with the **nearest valid edited value** in the same row or column.
- Handwritten numbers:
  - Remove non-decimal dots (e.g., `1.0.2` → `102`)
  - Replace horizontal line (`―`) with `000` (e.g., `12―` → `12000`)
- For invalid OCR-recognized Korean → **Do not fix or interpret**; return as-is.
- if duplicate rows are found, remove them and keep only one.
- Return only the full, valid JSON structure. No explanations or free text.

Do not generate multiple empty rows unless there are clearly duplicated actual rows that must be preserved.
### Special Case(지출 Table)

- only in "지출의 종류" column has a last 4 rows with side label `"외상구매", "카드구매"`:
  → Combine it as a prefix:  
  e.g., `외상판매: 수입종류값`
    """
    ,
    
    "자가농업 소비": """
    You will be provided part of scanned file that is splited in to 3  that contains a table with handwritten Korean text and numbers.  
  Extract data from the table accoring to the extration rules and return the result in the following JSON format.

The table name will follow this format:

- 자가농업 생산물 중 자가소비량 (N주차)
then the "차수" value will be "M"
Extract the table and return in the following JSON format.

### JSON Format

{
  "table_name": "자가농업 생산물 중 자가소비량",
  "table_data": [
    {
      "차수": [""],           // dtype: string (one of "1" ,"2","3","4" )
      "수입": [""],           // dtype: string (5-digit numeric string)
      "지출": [""],           // dtype: string (5-digit numeric string)
      "생산물": [""],         // dtype: string (korean text)
      "생산물 상세": [""],     // dtype: string (korean text)
      "용도": [""],           // dtype: string (korean text)
      "수량": [""],           // dtype: string (numeric or Korean text)
      "단위": [""],           // dtype: string (unit, e.g., kg, 근)
      "현물평가액": [""]       // dtype: string (numeric string for in-kind valuation)
    }
  ]
}

⚠️ Notes:
- The **dictionary keys must strictly follow the column order** as shown in each table's layout. Do not reorder or rename.
- Every value must be returned as a **list of strings**, even if the cell contains only one value.
- Do not infer or reassign fields based on context, value type, or content. **Use only the column position**.

### Extraction Rules

- Extract all rows **while maintaining accurate column alignment**.
- Assign values strictly based on **visual column structure**, not contextual meaning.
- All cell breaks occur based on column boundaries, not text content.
- For "수입" and "지출" columns:
  - Always determine based on visual layout. Do **not** infer based on numeric format.
  - The left column is always "수입", right is "지출".
  - These are 5-digit numeric fields with vertical bars (e.g., |1|2|3|4|5|). Remove bars and return as a stringified number (e.g., "12345").
- If handwriting crosses cell boundaries, infer the intended column based on **row structure** and alignment.
- If any cell is empty, return `[""]` for that field.
- Ditto marks (" ", `"`, `―`) → Replace with valid value **above** in the same column.
- Crossed-out values → Replace with the **nearest valid edited value** in the same row or column.
- Handwritten numbers:
  - Remove non-decimal dots (e.g., `1.0.2` → `102`)
  - Replace horizontal line (`―`) with `000` (e.g., `12―` → `12000`)
- For invalid OCR-recognized Korean → **Do not fix or interpret**; return as-is.
Do not generate multiple empty rows unless there are clearly duplicated actual rows that must be preserved.
- Return only the full, valid JSON structure. No explanations or free text.
    """
}



FORMAT_VALIDATION_TEMPLATE = {
    "임산물 현황":
        {"file_id": "",
         "page": "",
            "table_name": "임산물 현황",
             "지번": "",
              "지목": "",
              "읍면동": "",
              "가능면적(평)": "",
              "재배 작물명": "",
              "작물 부호": "",
              "면적": "",
              "주생산물 수확량": "",
              "주생산물 수확량 단위": "",
              "주생산물 판매량": "",
              "주생산물 판매량 단위": "",
              "부생산물 수확량": "",
              "부생산물 수확량 단위": "",
              "부생산물 판매량": "",
              "부생산물 판매량단위": ""
         },
        "자동이체_수입": {
            "file_id": "",
            "page": "",
            "table_name": "자동이체_수입",
            "수입": "",
            "지출": "",
            "재배형태": "",
            "수입의 종류": "",
            "수입원": "",
            "수량": "",
            "단위": "",
            "현금": ""
        },
        "자동이체_지출": {
            "file_id": "",
            "page": "",
            "table_name": "자동이체_지출",
            "수입": "",
            "지출": "",
            "지출의 종류": "",
            "용도": "",
            "수량": "",
            "단위": "",
            "현금": ""
        },
        "수입": {
            "file_id": "",
            "page": "",
            "table_name": "수입",
            "날": "",
            "짜": "",
            "유형": "",
            "수입": "",
            "지출": "",
            "재배형태": "",
            "수입의 종류": "",
            "수입원": "",
            "수량": "",
            "단위": "",
            "현금(원)": ""
        },
        "임업노동 투입내역": {
            "file_id": "",
            "page": "",
            "table_name": "임업노동 투입내역",
            "품목명": "",
            "품목 부호": "",
            "작업명": "",
            "작업 부호": "",
            "작업면적": "",
            "수확량": "",
            "단위": "",
            "노동투입시간 경영주": "",
            "노동투입시간 배우자": "",
            "가족노동 남": "",
            "가족노동 여": "",
            "고용노동 남": "",
            "고용노동 여": "",
            "품앗이 남": "",
            "품앗이 여": "",
            "일손돕기 남": "",
            "일손돕기 여": ""
        },
        "지출": {
            "file_id": "",
            "page": "",
            "table_name": "지출",
            "수입": "",
            "지출": "",
            "지출의 종류": "",
            "용도": "",
            "수량": "",
            "단위": "",
            "현금(원)": "",
            "현물(평가액)": ""
        },
        "동력사용시간": {
            "file_id": "",
            "page": "",
            "table_name": "동력사용시간",
            "명칭": "",
            "부호": "",
            "자가 시간": "",
            "임차 시간": ""
        },
        "자가임업생산물 중 자가소비량": {
            "file_id": "",
            "page": "",
            "table_name": "자가임업생산물 중 자가소비량",
            "수입": "",
            "지출": "",
            "생산물": "",
            "용도": "",
            "수량": "",
            "단위": "",
            "현물평가액": ""
        },
        "자가농업 생산물 중 자가소비량": {
            "file_id": "",
            "page": "",
            "table_name": "자가농업 생산물 중 자가소비량",
            "차수": "",
            "수입": "",
            "지출": "",
            "생산물": "",
            "생산물 상세": "",
            "용도": "",
            "수량": "",
            "단위": "",
            "현물평가액": ""
        }
}

MUST_INCLUDE = [ '임가번호', '경영주 성명', '날', '짜', '수입 부호']


FINAL_DF_FORMAT = {"임산물 현황": 
                        {"coiumns": 
                            ["임가번호", "경영주 성명", "지번", "지목", "읍면동", 
                                "가능면적(평)", "재배 작물명", "작물 부호", 
                                "면적", "주생산물 수확량", "주생산물 수확량 단위", "주생산물 판매량", 
                                "주생산물 판매량 단위", "부생산물 수확량", "부생산물 수확량 단위",
                                "부생산물 판매량", "부생산물 판매량 단위"],
                
                             "rename" : 
                                 ["임가번호", "경영주 성명", "지번", "지목", "읍면동", 
                                    "가능면적(평)", "재배 작물명", "작물 부호", 
                                    "면적", "주생산물 수확량", "단위", "주생산물 판매량", 
                                    "단위", "부생산물 수확량", "단위",
                                    "부생산물 판매량", "단위"]},
                   "자동이체_수입" :
                       {"coiumns":
                           ["임가번호","경영주 성명","유형",
                            '수입', '지출', '재배형태', '수입의 종류', '수입원',
                            '수량', '단위', '현금'],
                       
                       "rename": 
                           ["임가번호", "경영주 성명", "유형",
                            "수입 부호", "지출 부호", "재배형태 코드", 
                            "수입(지출)의 종류",
                             "수입원(용도)", "수량", "단위", "현금(원)"]},
                     "자동이체_지출" :
                          {"coiumns":
                                ["임가번호","경영주 성명","유형",
                                '수입', '지출',"재배형태 코드", '지출의 종류',  '용도', 
                                '수량', '단위', '현금'],
                          
                          "rename": 
                                ["임가번호", "경영주 성명", "유형",
                                "수입 부호", "지출 부호", "재배형태 코드", 
                                "지출(수입)의 종류",
                                "지출원(용도)", "수량", "단위", "현금(원)"]},
                    "수입" :
                        {"coiumns":
                                ["임가번호","경영주 성명",'날', '짜', '유형', 
                                '수입', '지출', '재배형태','수입의 종류', 
                                '수입원', '수량', '단위', '현금(원)', '현물(평가액)'],


                          "rename": 
                                ["임가번호", "경영주 성명", "날","찌", "유형",
                                "수입 부호", "지출 부호", "재배형태 코드", 
                                "수입(지출)의 종류",
                                "수입원(용도)", "수량", "단위",  "현금(원)", "현물(평가액)"]},
                        
                    "지출" :
                        {"coiumns":
                                ["임가번호","경영주 성명",'날', '짜', '유형', 
                                 '수입', '지출', "재배형태 코드", 
                                 '지출의 종류', 
                                 '용도','수량',  '단위', '현금(원)', '현물(평가액)'],
                            
                        "rename": 
                                ["임가번호", "경영주 성명", "날","찌", "유형",
                                "수입 부호", "지출 부호", "재배형태 코드", 
                                "수입(지출)의 종류",
                                "수입원(용도)", "수량", "단위",  "현금(원)", "현물(평가액)"]},
                        
                    "임업노동 투입내역":
                        {"coiumns":
                                ["임가번호","경영주 성명", '날', '짜', '품목명', '품목 부호',
                                 '작업명','작업 부호', '작업면적', '수확량', '단위',
                                '노동투입시간 경영주', '노동투입시간 배우자', '가족노동 남', 
                                '가족노동 여','고용노동 남', '고용노동 여', '품앗이 남',
                                '품앗이 여', '일손돕기 남', '일손돕기 여'],
                            
                        "rename": 
                                ["임가번호","경영주 성명", '날', '짜', '품목명', '품목 부호',
                                 '작업명','작업 부호', '작업면적', '수확량', '단위',
                                '노동투입시간 경영주', '노동투입시간 배우자', '가족노동 남', 
                                '가족노동 여','고용노동 남', '고용노동 여', '품앗이 남',
                                '품앗이 여', '일손돕기 남', '일손돕기 여']},
                    "동력사용시간":
                        {"coiumns":
                                ["임가번호","경영주 성명", '날', '짜', '명칭', '부호', '자가 시간', '임차 시간'],
                            
                        "rename": 
                                ["임가번호","경영주 성명", '날', '짜', "명칭","부호","자가시간","임차시간"]},
                    "자가임업생산물 중 자가소비량":
                        {"coiumns":
                                ["임가번호","경영주 성명", '날', '짜', '수입', '지출', '생산물',
                                 '용도','수량','단위', '현물평가액'],

                            
                        "rename": 
                                ["임가번호","경영주 성명", '날', '짜', '수입 부호', '지출 부호',
                                 '생산물','용도','수량','단위','현물평가액']},
                    "자가농업 생산물 중 자가소비량":
                        {"coiumns":
                                ["임가번호","경영주 성명", '차수', '수입', '지출', 
                                 '생산물', '생산물 상세',
                                    '용도', '수량', '단위', '현물평가액'],

                            
                        "rename": 
                                ["임가번호","경영주 성명",'차수', '수입 부호', '지출 부호', 
                                 '생산물', '생산물 상세',
                                    '용도', '수량', '단위', '현물평가액']},
                        
    }

PAGE_MAP = {
    "09": ["임산물 현황"],
    "10": ["자동이체_수입"],
    "11": ["자동이체_지출"],
    "12": ["수입", "임업노동 투입내역"],
    "13": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "14": ["수입", "임업노동 투입내역"],
    "15": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "16": ["수입", "임업노동 투입내역"],
    "17": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "18": ["수입", "임업노동 투입내역"],
    "19": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "20": ["자가농업 생산물 중 자가소비량"],
    "21": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "22": ["수입", "임업노동 투입내역"],
    "23": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "24": ["수입", "임업노동 투입내역"],
    "25": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "26": ["수입", "임업노동 투입내역"],
    "27": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "28": ["수입", "임업노동 투입내역"],
    "29": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "30": ["자가농업 생산물 중 자가소비량"],
    "31": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "32": ["수입", "임업노동 투입내역"],
    "33": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "34": ["수입", "임업노동 투입내역"],
    "35": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "36": ["수입", "임업노동 투입내역"],
    "37": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "38": ["수입", "임업노동 투입내역"],
    "39": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "40": ["자가농업 생산물 중 자가소비량"],
    "42": ["수입", "임업노동 투입내역"],
    "43": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "44": ["수입", "임업노동 투입내역"],
    "45": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "46": ["수입", "임업노동 투입내역"],
    "47": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "48": ["수입", "임업노동 투입내역"],
    "49": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "50": ["수입", "임업노동 투입내역"],
    "51": ["지출", "동력사용시간", "자가임업생산물 중 자가소비량"],
    "52": ["자가농업 생산물 중 자가소비량"]
}

DATE_MAPPER = {"12":(1,2), "13":(1,2),
                "14":(3,4), "15":(3,4),
                "16":(5,6), "17":(5,6),
                "18":(7,7), "19":(7,7),
                "22":(8,9), "23":(8,9),
                "24":(10,11), "25":(10,11),
                "26":(12,13), "27":(12,13),
                "28":(14,''), "29":(14,''),
                "32":(15,16), "33":(15,16),
                "34":(17,18), "35":(17,18),
                "36":(19,20), "37":(19,20),
                "38":(21,''), "39":(21,''),
                "42":(22,23), "43":(22,23),
                "44":(24,25), "45":(24,25),
                "46":(26,27), "47":(26,27),
                "48":(28,29), "49":(28,29),
                "50":(30,31), "51":(30,31)}

