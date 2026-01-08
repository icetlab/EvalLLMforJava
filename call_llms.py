from openai import OpenAI
from google import genai
# import anthropic
from google.genai import types

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

persona = read_file("persona.txt")

def improve_code_with_gpt(prompt):
    # OpenAI-o4-mini
    client = OpenAI(
        api_key=""
    )
    response = client.responses.create(
        model="o4-mini",
        reasoning={"effort": "medium"},
        input=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        top_p=0.95,
    )
    return response.output_text

def improve_code_with_deepseek_v3(prompt):
    # DeepSeek-V3
    client = OpenAI(api_key="", base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        temperature=0.3,
        top_p=0.95,
    )
    return response.choices[0].message.content

def improve_code_with_deepseek_r1(prompt):
    # DeepSeek-R1
    client = OpenAI(api_key="", base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        temperature=0.3,
        top_p=0.95,
    )
    return response.choices[0].message.content

def improve_code_with_gemini(prompt):
    # Google-Gemini-2.5-Pro
    client = genai.Client(api_key="")

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        config=types.GenerateContentConfig(
            system_instruction=persona,
            temperature=0.3,
            top_p=0.95,
        ),
        contents=prompt
    )
    return response.text

def call_llm(model_name, prompt):
    if model_name == "gpt":
        return improve_code_with_gpt(prompt)
    elif model_name == "gemini":
        return improve_code_with_gemini(prompt)
    # elif model_name == "llama":
    #     return improve_code_with_llama(prompt)
    elif model_name == "deepseek-v3":
        return improve_code_with_deepseek_v3(prompt)
    elif model_name == "deepseek-r1":
        return improve_code_with_deepseek_r1(prompt)
    # elif model_name == "claude":
    #     return improve_code_with_claude(prompt)
    else:
        raise ValueError("Unsupported model name. Choose from 'gpt' or 'gemini'.")
