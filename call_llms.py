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
    else:
        raise ValueError("Unsupported model name. Choose from 'gpt' or 'gemini'.")
