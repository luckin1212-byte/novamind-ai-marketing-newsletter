# performance_analysis.py
import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import random

def analyze_performance():
    # Load environment variables
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # 模拟每个 persona 的表现数据
    personas = ["Founder", "Creative Professional", "Operations Manager"]
    performance_data = {}

    for persona in personas:
        performance_data[persona] = {
            "open_rate": round(random.uniform(0.3, 0.7), 2),
            "click_rate": round(random.uniform(0.1, 0.4), 2),
            "unsubscribe_rate": round(random.uniform(0.0, 0.05), 2)
        }

    # 保存到 performance_log.json
    log_filename = "performance_log.json"
    with open(log_filename, "w") as f:
        json.dump(performance_data, f, indent=2)
    print(f"✅ Performance data saved to {log_filename}")

    # 用 AI 生成分析总结
    prompt = f"""
    You are a marketing analyst. Here is the newsletter performance data by persona:
    {json.dumps(performance_data, indent=2)}
    Write a short summary in 2-3 sentences. Include which persona performed best and one suggestion for next campaign.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful marketing analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        summary = response.choices[0].message.content.strip()
    except Exception as e:
        summary = f"Error generating AI summary: {str(e)}"

    return summary, performance_data
