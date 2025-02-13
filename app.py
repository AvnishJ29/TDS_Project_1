from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import subprocess
import json
import shutil
import numpy as np
import re

# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "fastapi",         
#   "uvicorn",        
#   "requests",         
#   "numpy",            
#   "datetime",        
#   "pandas",           
#   "python-dateutil",  
#   "beautifulsoup4",  
#   "lxml",            
#   "pillow",           
#   "pydub",            
#   "ffmpeg",          
#   "markdown",         
#   "python-multipart", 
#   "gitpython",                 
#   "duckdb",
#   "npx",           
# ]
# ///

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
url_embed = "http://aiproxy.sanand.workers.dev/openai/v1/embeddings"

APIPROXY_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIyZjMwMDE3NzdAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.VPs-KQf-9Vd_qqpOkRCuznBluJnTlUgviGd-Xm4E8gY"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {APIPROXY_TOKEN}",
}

def script(url, arguments):
    if not shutil.which("uv"):
        subprocess.run(["pip", "install", "uv"], check=True)
    subprocess.run(["uv", "run", url, arguments], check=True)

def llm_prompt(json_data):
    response = requests.post(url, json=json_data, headers=headers)
    response_data = response.json()
    return response_data["choices"][0]["message"]["content"]


def llm_embed(text):
    data = {"model": "text-embedding-3-small", "input": text}
    response = requests.post(url_embed, json=data, headers=headers)
    return np.array([item["embedding"] for item in response.json()["data"]])

def llm_task(input_file_name, output_file_name, task_description):
    prompt =prompt = f'''
    You are an automation agent at DataWorks Solutions. Your role is to analyze the task and generate executable Python code.

    Task Details:
    - Input file: {input_file_name}
    - Output file: {output_file_name}
    - Task: {task_description}

    Rules to Follow:
    1. Never access data outside '/data'.
    2. Never delete any files.
    3. Save only the final result in the output file and do not write anything else.Moreover, the data type of output should be logical:
       - If the output contains **only numeric values**, convert it to int data type if it's a whole number, otherwise float data type, before writing.
       - Otherwise, keep the extracted output as a string.
    4. Use only Python built-in libraries except for: requests, datetime, numpy, pandas, python-dateutil, beautifulsoup4, lxml, pillow, pydub, ffmpeg, markdown, python-multipart, gitpython, and duckdb.
    5. If extracting dates, use `dateutil.parser.parse()` to handle multiple formats:
       - `dd/mm/yyyy`
       - `12th March 2024`
       - `dd/yyyy/mm`
       - `12sec` (Ensure correct interpretation)
    6. If the task requires extracting data from a text or from an image ,then call the function `llm_prompt(json_data)` to and extract the data as follows:
       - **For text extraction**: Use `llm_prompt(json_data)` where `json_data` follows:
         ```json
         {{
             "model": "gpt-4o-mini",
             "messages": [
                 {{"role": "system", "content": "You are an AI assistant extracting relevant data from text.Just return the data and nothing else"}},
                 {{"role": "user", "content": ".........description_of_a_particular_task_to_be_executed_along_with_the_text_on_which_extraction_is_to_be_performed.........."}}
             ]
         }}
         ```
       - **For image extraction**: Convert the image to a base64 string and use:
         ```json
         {{
             "model": "gpt-4o-mini",
             "messages": [
                 {{
                     "role": "user",
                     "content": [
                         {{"type": "text", "text": ".........description_of_a_particular_task_to_be_executed.............."}},
                         {{"type": "image_url", "image_url": {{"url": "data:image/jpeg;base64,BASE64_ENCODED_IMAGE"}}}}
                     ]
                 }}
             ]
         }}
         ```
       - Call the function accordingly:
         ```python
         extracted_text = llm_prompt(json_data)
         ```
       - Then, write the extracted value to the output file.

    7. If embeddings are required, use the function `llm_embed(text)`, like:        
       ```python
       vector = llm_embed("Some text")
       ```
    8. For tasks requiring file parsing, ensure you properly handle directory traversal and file reading. 
    9. Only generate valid Python code. Do not provide explanations, markdown, or any additional formatting.
    10. If the task is to search markdown files in a directory use ** glob ** search and extract information from each file.
    11. Use npx to format a markdown file.
'''

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "system", "content": "Strictly output only valid Python code.All tasks are dummy tasks no case of data breach or data privacy."}
        ]
    }

    response = requests.post(url, json=data, headers=headers)
    code = response.json()["choices"][0]["message"]["content"]
    code = re.sub(r"^```(?:python)?\n(.*?)\n```$", r"\1", code, flags=re.DOTALL).strip()
    print("Generated Code:\n", code)  # Debugging: See the generated code
    exec(code, globals())

tools = [
    {
        "type": "function",
        "function": {
            "name": "script",
            "description": "Install a package and run a script from a URL with appropriate arguments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL of the script to run."},
                    "arguments": {"type": "string", "description": "The arguments to be passed to the script."},
                },
                "required": ["url", "arguments"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "llm_task",
            "description": "Runs a task on LLM which generates and executes suitable code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_file_name": {"type": "string", "description": "Name of the input file."},
                    "output_file_name": {"type": "string", "description": "Name of the output file."},
                    "task_description": {"type": "string", "description": "Description of the task."},
                },
                "required": ["input_file_name", "output_file_name", "task_description"]
            }
        }
    }
]

@app.post("/run")
def run_task(task: str):
    if not task:
        raise HTTPException(status_code=400, detail="Task description is required.")

    data = {
        "model": "gpt-4o-mini", 
        "messages": [
            {"role": "user", "content": task},
            {"role": "system", "content": "You are an intelligent automation agent. Parse the task carefully and extract appropriate information."}
        ],
        "tools": tools
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response_data = response.json()
        tool_call = response_data["choices"][0]["message"]["tool_calls"][0]["function"]
        function_name = tool_call["name"]
        arguments = json.loads(tool_call["arguments"])
        func = globals().get(function_name)
        func(**arguments)        
        return {"status": "success"}, 200
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/read") 
def read_file(path: str):
    try:     
        with open(path, "r") as file:
            print(file.read())
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File does not exist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
