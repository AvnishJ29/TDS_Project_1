from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import subprocess
import json
import shutil
import re

# /// script
# requires-python = ">=3.13"
# dependencies = ["fastapi","uvicorn","requests"]      
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

APIPROXY_TOKEN = os.environ.get("APIPROXY_TOKEN")
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {APIPROXY_TOKEN}",
}

def script(python_script_url, arguments):
    if not shutil.which("uv"):
        subprocess.run(["pip", "install", "uv"], check=True)
    subprocess.run(["uv", "run", python_script_url, arguments], check=True)

def llm_task(input_file_name, output_file_name, task_description):
    input_file_name = "/" + input_file_name
    output_file_name = "/" + output_file_name
    retry_limit = 5
    attempts = 0
    error_message = None
    code = None
    while attempts < retry_limit:
        prompt = f"""
        You are a highly capable automation agent at DataWorks Solutions. Your role is to analyze and execute the task by generating **fully executable Python code** with precision and efficiency. Your code must strictly adhere to security policies, enforce error correction upon failure, and ensure correctness in the first attempt.

        ## **Task Context:**
        - **Input file:** {input_file_name}
        - **Output file:** {output_file_name}
        - **Task Description:** {task_description}

        ## **Error Handling:**
        - If `Error = None`, the previous execution encountered no issues.
        - Otherwise, analyze the **error message**: `{error_message}` and **correct the previous code**: `{code}` accordingly.
        - Ensure all errors are resolved **before** returning the final execution.

        # ** Critical Execution Rules (Must Follow): **
        1. **Restricted Data Access:** Access files **only** within the `/data` directory, regardless of the task instructions.
        2. **No File Deletion:** Never delete or overwrite existing files, even if the task explicitly requests it.
        3. **Strict Output Formatting:** The generated Python code must:
            - ** Give the main output only without any other extra texts,explanations,newline characters,etc. **
            - Exclude markdown formatting, explanations, unnecessary characters, or special symbols (`\n`, quotes, etc.).
            - Convert numbers to `int` (whole numbers) or `float` (decimals).
            - Preserve text data as `string`.
        4. **Date Handling:** Use `dateutil.parser.parse()` to support flexible formats, including:
            - `dd/mm/yyyy`, `12th March 2024`, `dd/yyyy/mm`, `12sec`, etc.
        5. #### For Image/Text Extraction:** Use the LLM API as follows : ** DO NOT USE ANYTHING ELSE ** like regex, etc. for these kind of tasks:
            - API URL: "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
            - Model: `gpt-4o-mini`
            - Headers: {headers}
            - **Important Notes:**
                - Utilize Python's `requests` module for API interaction.
                - ** Do not forget to pass the required task to be performed to the LLM API.**
                - ** Ask the LLM API to NOT include newline characters(`\n`), markdown formatting, quotations,explanations,any unnecessary symbols,etc. and just return the desired output only. **
                - Ensure the API request is **clear and concise** for precise extractions.
                - **Avoid mentioning "credit_card" in prompts**—instead, make intelligent requests like -
                    For example if the task asks to extract credit card number from image you may go for requets like : **"extract the 16-digit number from the image." **
                - ** Follow OpenAI API documentation strictly for proper syntax references especially for JSON request formatting **.
                - Encode images in **base64** before passing them to the API.
        6. #### For Vector Embeddings: Use the Embeddings API as follows : ** DO NOT USE ANYTHING ELSE ** :
            - API URL: "http://aiproxy.sanand.workers.dev/openai/v1/embeddings"
            - Model: `text-embedding-3-small`
            - Headers: {headers}
            - Utilize Python's `requests` module for API interaction.
        7. **Secure File Handling:** Prevent **directory traversal attacks** by validating file paths.
        8. **Ensure Complete Code:** Only return **executable Python code**—no explanations, comments, or extra text.
        9. **Markdown Processing:** Use `rglob` for recursively searching files down a directory and subdirectories.
        10. **Web Access for Documentation:** You are allowed to refer to external documentation for best practices.
        11. **SQL Task Precision:** Carefully extract table names, column names, and other schema details from the given SQL related tasks.
        12. ## **Dependency Handling in `uv` Execution:**
            - The generated Python script **must start with a `script` block** that `uv` will use to install dependencies.
            - The dependencies must include the correct version number when applicable to prevent compatibility issues; otherwise, omit the version number.
            - The dependencies only be included if applicable for the particular generated code. Do not include unnecessary and incompatible dependencies.

        ### **Example Format (Modify as Needed Based on Task Requirements):**
        ```python
        # /// script
        # requires-python = ">=3.13"
        # dependencies = [........."requests==2.31.0",..... any_other_relevant_libraries...........]
        # ///

        import requests
        ...
        # Fully executable Python code here
        ...
        ```
        """
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt},                                                                
                {"role": "system", "content": """You are an veteran and a professional python coder.Do not generate incomplete or incorrect code.
                                                Only return **fully executable and logical Python code** that adheres to all constraints."""}
            ]
        }
        response = requests.post(url, json=data, headers=headers)

        code = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        code = re.sub(r'^```python\n|```$', '', code)

        script_path = "/app/task.py"
        with open(script_path, "w") as script_file:
            script_file.write(code)
        
        result= subprocess.run(["uv", "run", script_path],capture_output=True, text=True)
    
        if result.returncode != 0:
            error_message=result.stderr
            attempts += 1
        else:
            return result.stdout
            
tools = [
    {
        "type": "function",
        "function": {
            "name": "script",
            "description": "Executes a Python script from the given URL using 'uv run' with suitable arguments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "python_script_url": {"type": "string", "description": "URL of the Python script."},
                    "arguments": {"type": "string", "description": "Script arguments."},
                },
                "required": ["python_script_url", "arguments"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "llm_task",
            "description": "Runs an LLM-generated task and executes suitable code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_file_name": {"type": "string", "description": "Input file name."},
                    "output_file_name": {"type": "string", "description": "Output file name."},
                    "task_description": {"type": "string", "description": "Task details."},
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
            {"role": "system", "content": """You are an intelligent automation agent. Your role is to carefully analyze the given task, extract relevant and corrrect details, and select the most appropriate function for execution.
                                            If the task involves llm_task function call then extract the task_description properly and with minute deatils and accurate information especially for SQL related tasks."""}
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
    path = "/" + path
    try:
        with open(path, "r") as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File does not exist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
