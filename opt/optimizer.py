"""optimizer.py — 调用 Optimizer LLM 分析回测错误，生成有界编辑提案

输入: opt/input/rollout.json (由 collector.py 生成)
输出: opt/output/edits.json (结构化编辑提案)

Optimizer LLM: 使用 DeepSeek-V4，仅离线调用（部署时不需要）
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from openai import OpenAI

INPUT_DIR = PROJECT_DIR / "opt" / "input"
OUTPUT_DIR = PROJECT_DIR / "opt" / "output"
SKILLS_DIR = PROJECT_DIR / "skills"


def load_optimizer_prompt():
    prompt_file = Path(__file__).parent / "optimizer_prompt.md"
    return prompt_file.read_text(encoding="utf-8")


def build_user_message(rollout_data: dict) -> str:
    """构建给 Optimizer 的用户消息，包含回测摘要和当前 skills。"""
    summary = rollout_data.get("group_summary", {})
    overall = summary.get("overall", {})

    msg = "# Backtest Summary\n\n"
    msg += "Overall: {hit} HIT, {avoid} AVOID, {miss} MISS, {step} STEP ".format(**overall)
    msg += "(accuracy: {acc}%)\n\n".format(acc=overall.get("accuracy", 0))

    # Sector breakdown
    msg += "## By Sector\n\n"
    for sector, s in summary.get("by_sector", {}).items():
        msg += "- {sec}: {hit}H/{avoid}A/{miss}M/{step}S (acc {acc}%)\n".format(
            sec=sector, hit=s["hit"], avoid=s["avoid"],
            miss=s["miss"], step=s["step"], acc=s["accuracy"]
        )

    # MISS cases
    miss_cases = summary.get("by_error_type", {}).get("MISS", [])
    if miss_cases:
        msg += "\n## MISS Cases (Buy but fail)\n\n"
        for c in miss_cases[:5]:
            msg += "- {date} {stock}({sector}): pred {rating} {conf:.0%}, actual {chg:+.2f}%\n".format(
                date=c["date"], stock=c["stock"], sector=c["sector"],
                rating=c["rating"], conf=c["confidence"], chg=c["actual_chg"]
            )

    # STEP cases
    step_cases = summary.get("by_error_type", {}).get("STEP", [])
    if step_cases:
        msg += "\n## STEP Cases (Hold but up >=1%)\n\n"
        for c in step_cases[:10]:
            msg += "- {date} {stock}({sector}): pred {rating} {conf:.0%}, actual {chg:+.2f}%\n".format(
                date=c["date"], stock=c["stock"], sector=c["sector"],
                rating=c["rating"], conf=c["confidence"], chg=c["actual_chg"]
            )

    # Current skill files
    msg += "\n## Current Skill Files (SKILLOPT-EDITABLE regions only)\n\n"
    skill_files = rollout_data.get("skill_files", {})
    for skill_name in ["bull_researcher", "bear_researcher", "portfolio_manager",
                       "trader", "research_manager"]:
        content = skill_files.get(skill_name, "")
        if content:
            # Only include the editable sections to save tokens
            msg += "### {}\n```markdown\n{}\n```\n\n".format(skill_name, content[:3000])

    return msg


def run_optimizer(rollout_path: str = None) -> dict:
    """Run the Optimizer LLM and return edit proposals.

    Args:
        rollout_path: Path to rollout.json. Default: opt/input/rollout.json

    Returns:
        {"analysis": "...", "edits": [...], "meta": {...}}
    """
    if rollout_path is None:
        rollout_path = INPUT_DIR / "rollout.json"

    rollout_path = Path(rollout_path)
    if not rollout_path.exists():
        return {"error": "rollout.json not found at {}".format(rollout_path), "edits": []}

    rollout_data = json.loads(rollout_path.read_text(encoding="utf-8"))

    system_prompt = load_optimizer_prompt()
    user_message = build_user_message(rollout_data)

    # Initialize client
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not api_key:
        return {"error": "DEEPSEEK_API_KEY not set", "edits": []}

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        return {"error": "Optimizer LLM call failed: {}".format(e), "edits": []}

    try:
        result = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {"error": "Optimizer returned invalid JSON", "edits": []}

    result["meta"] = {
        "timestamp": datetime.now().isoformat(),
        "rollout_date_range": rollout_data.get("date_range", "?"),
        "total_results": len(rollout_data.get("rollout_results", [])),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "edits.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Optimizer output saved to: {}".format(output_path))
    if result.get("analysis"):
        print("Analysis: {}".format(result["analysis"][:120]))
    print("Edits: {} proposals".format(len(result.get("edits", []))))

    return result


if __name__ == "__main__":
    result = run_optimizer()
    print(json.dumps(result, ensure_ascii=False, indent=2))
