import os
import transformers
import torch
from openai import OpenAI
from google import genai
from google.genai import types
import anthropic

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

persona = read_file("persona.txt")

def improve_code_with_gpt(prompt):
    # OpenAI-o4-mini
    client = OpenAI(
        api_key="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"
    )
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        top_p=0.95,
    )
    return  completion.choices[0].message.content

def improve_code_with_llama(prompt):
    # Meta-Llama-3.1-8B-Instruct
    model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    pipeline = transformers.pipeline(
        "text-generation",
        model=model_id,
        model_kwargs={"torch_dtype": torch.bfloat16},
        device_map="auto",
    )
    messages=[
        {"role": "system", "content": persona},
        {"role": "user", "content": prompt},
    ]
    outputs = pipeline(
        messages,
        do_sample=True,
        temperature=0.3,
        top_p=0.95,
    )
    assistant_response = outputs[0]["generated_text"]
    if isinstance(assistant_response, str):
        return assistant_response.strip()
    else:
        return str(assistant_response).strip()

def improve_code_with_deepseek(prompt):
    # DeepSeek-V3
    client = OpenAI(api_key="sk-f43d955ae076497ba2ca4c507d04d8ba", base_url="https://api.deepseek.com")
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

def improve_code_with_gemini(prompt):
    # Google-Gemini-2.5-Pro
    client = genai.Client(api_key="AIzaSyCgvKD7ZSc4mfcHIAzhZ_yAdZp3xYfZBls")

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        top_p=0.95,
    )
    return response.choices[0].message.content

def improve_code_with_claude(prompt):
    # Anthropic-Claude-4-Sonnet
    client = anthropic.Anthropic(api_key="sk-ant-api03-8dC9xk5DJ4TzpLzhAfKRsVQdGoTR_5UYq998ziNOZUDz49zOXnyxMgMmBxJz1LIrZhEJtBUcANT3BlbkFJquiLRnpv11d7HPdIwRVTD2indjS9M7ghxOCVo4jbOTY82-BRMmXVr5_r-Hm2JXuwPoK2U7J1gA")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        top_p=0.95,
    )
    return message.content

def call_llm(model_name, prompt):
    if model_name == "gpt":
        return improve_code_with_gpt(prompt)
    elif model_name == "llama":
        return improve_code_with_llama(prompt)
    elif model_name == "deepseek":
        return improve_code_with_deepseek(prompt)
    elif model_name == "gemini":
        return improve_code_with_gemini(prompt)
    elif model_name == "claude":
        return improve_code_with_claude(prompt)
    else:
        raise ValueError("Unsupported model name. Choose from 'gpt', 'llama', 'deepseek', claude, or 'gemini'.")
