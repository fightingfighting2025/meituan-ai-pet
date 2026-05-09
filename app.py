# app.py
# -*- coding: utf-8 -*-

import json
import re
import streamlit as st
from openai import OpenAI


# =========================
# 固定 DeepSeek 模型配置
# =========================
API_KEY = "sk-0bad31b0174e4f1ca6299f23d5dce711"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

EXP_PER_LEVEL = 30


# =========================
# 页面配置
# =========================
st.set_page_config(
    page_title="AI 运动电子宠物",
    page_icon="🏃",
    layout="centered"
)


# =========================
# 页面美化 CSS
# =========================
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 900;
        text-align: center;
        padding: 20px 12px;
        margin-bottom: 18px;
        border-radius: 24px;
        background: linear-gradient(135deg, #111827, #1f2937, #0f766e);
        color: white;
        box-shadow: 0 12px 35px rgba(0,0,0,0.20);
    }

    .pet-card {
        padding: 22px;
        border-radius: 22px;
        background: linear-gradient(135deg, #fff7ed, #ecfeff);
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 10px 28px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }

    .pet-name {
        font-size: 1.4rem;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .reply-box {
        padding: 18px;
        border-radius: 18px;
        background: linear-gradient(135deg, #f0fdf4, #eff6ff);
        border-left: 6px solid #22c55e;
        font-size: 1.05rem;
        line-height: 1.8;
        margin-top: 16px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.06);
    }

    .level-up-box {
        padding: 18px;
        border-radius: 18px;
        background: linear-gradient(135deg, #fef3c7, #ffedd5);
        border-left: 6px solid #f59e0b;
        font-size: 1.08rem;
        font-weight: 700;
        line-height: 1.8;
        margin-top: 16px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    }

    .info-box {
        padding: 15px 18px;
        border-radius: 16px;
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        color: #374151;
        line-height: 1.7;
        margin-bottom: 15px;
    }

    .small-tip {
        color: #6b7280;
        font-size: 0.92rem;
    }

    .stButton button {
        width: 100%;
        border-radius: 16px;
        height: 3.1rem;
        font-size: 1.08rem;
        font-weight: 800;
        background: linear-gradient(135deg, #22c55e, #14b8a6);
        color: white;
        border: none;
    }

    .stButton button:hover {
        background: linear-gradient(135deg, #16a34a, #0f766e);
        color: white;
        border: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# =========================
# Session State 初始化
# =========================
if "level" not in st.session_state:
    st.session_state.level = 1

if "exp" not in st.session_state:
    st.session_state.exp = 0

if "total_checkins" not in st.session_state:
    st.session_state.total_checkins = 0

if "last_reply" not in st.session_state:
    st.session_state.last_reply = ""

if "last_reward" not in st.session_state:
    st.session_state.last_reward = 0

if "just_leveled_up" not in st.session_state:
    st.session_state.just_leveled_up = False

if "last_level" not in st.session_state:
    st.session_state.last_level = 1


# =========================
# 工具函数
# =========================
def extract_json_from_text(text: str) -> dict:
    """
    从模型输出中提取 JSON。
    兼容：
    1. 纯 JSON
    2. ```json ... ```
    3. 前后夹杂少量解释文本
    """
    if not text:
        raise ValueError("模型返回内容为空。")

    text = text.strip()

    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("无法从模型返回内容中解析 JSON。")


def normalize_exp_reward(value) -> int:
    """
    保证经验值一定是 10 到 50 之间的整数。
    """
    try:
        exp = int(value)
    except Exception:
        exp = 10

    return max(10, min(50, exp))


def call_ai_pet(sport_text: str) -> dict:
    """
    调用 DeepSeek 模型，分析用户运动打卡内容。
    """
    if not API_KEY or API_KEY == "这里填你的 DeepSeek API Key":
        raise RuntimeError("请先在代码顶部填写 DeepSeek API Key。")

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL
    )

    system_prompt = """
你是一只“AI运动电子宠物”，性格傲娇、可爱，但非常关心主人健康。
你需要分析用户今天的运动打卡内容。

你的任务：
1. 提取用户的“运动类型”。
2. 判断用户的“运动强度”，只能从以下三个里选：低强度 / 中强度 / 高强度。
3. 用宠物的傲娇、鼓励、可爱口吻回复一段话。
4. 根据运动情况给出 10 到 50 之间的整数经验值奖励。

经验值规则参考：
- 内容很少、运动量不明确、只是轻微活动：10-20
- 普通运动，如散步、慢跑、健身、骑行等：20-35
- 较高强度或较长时间运动：35-50
- 如果用户没有真正运动，也要温柔提醒，并给 10 分左右。

你必须只返回 JSON，不要返回 Markdown，不要返回解释文字。

JSON 格式必须严格如下：
{
  "reply_text": "宠物回复文本",
  "exp_reward": 30
}
"""

    user_prompt = f"""
用户今天的运动打卡内容：

{sport_text}

请只返回 JSON。
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0.8
    )

    content = response.choices[0].message.content
    data = extract_json_from_text(content)

    reply_text = str(data.get("reply_text", "")).strip()
    exp_reward = normalize_exp_reward(data.get("exp_reward", 10))

    if not reply_text:
        reply_text = "哼，虽然你写得有点简单，但本宠物还是感受到了一点点运动能量！下次要更认真打卡哦！"

    return {
        "reply_text": reply_text,
        "exp_reward": exp_reward
    }


def add_exp(exp_reward: int) -> bool:
    """
    增加经验值。
    EXP 满 30 后升级。

    重点：
    - 初始 Lv1。
    - EXP 达到 30 后立刻升到 Lv2。
    - 升到 Lv2 就会触发特效。
    """
    old_level = st.session_state.level

    st.session_state.exp += exp_reward

    while st.session_state.exp >= EXP_PER_LEVEL:
        st.session_state.level += 1
        st.session_state.exp -= EXP_PER_LEVEL

    new_level = st.session_state.level

    return new_level > old_level


# =========================
# Sidebar
# =========================
with st.sidebar:
    st.header("🐾 宠物档案")

    st.markdown(
        f"""
        <div class="info-box">
        🧬 <b>当前模型：</b>{MODEL_NAME}<br>
        🌐 <b>接口地址：</b>{BASE_URL}<br>
        🔐 <b>API Key：</b>代码内固定配置<br>
        🎯 <b>升级规则：</b>{EXP_PER_LEVEL} EXP 升 1 级
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    st.write("📌 使用说明")
    st.write("1. 输入今天的运动内容")
    st.write("2. 点击提交打卡")
    st.write("3. AI 宠物会分析运动并奖励 EXP")
    st.write("4. 从 Lv1 升到 Lv2 就会触发庆祝特效 🎉")

    st.divider()

    if st.button("🔄 重置宠物数据"):
        st.session_state.level = 1
        st.session_state.exp = 0
        st.session_state.total_checkins = 0
        st.session_state.last_reply = ""
        st.session_state.last_reward = 0
        st.session_state.just_leveled_up = False
        st.session_state.last_level = 1
        st.success("宠物数据已重置！")
        st.rerun()


# =========================
# Main Area
# =========================
st.markdown(
    '<div class="main-title">🏃 AI 运动电子宠物：喂养你的数字生命</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="pet-card">
        <div class="pet-name">🐣 你的电子宠物正在待机中</div>
        <div>
        它眨着眼睛看着你：<b>“今天有没有运动呀？别想骗本宠物，本宠物可是会分析的！”</b>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("🌟 等级 Lv", st.session_state.level)

with col2:
    st.metric("⚡ 当前 EXP", f"{st.session_state.exp} / {EXP_PER_LEVEL}")

with col3:
    st.metric("📅 累计打卡", st.session_state.total_checkins)

st.progress(st.session_state.exp / EXP_PER_LEVEL)

st.markdown(
    '<p class="small-tip">每次打卡可获得 10-50 EXP。从 Lv1 升到 Lv2 就会触发庆祝特效 🎉</p>',
    unsafe_allow_html=True
)

if st.session_state.just_leveled_up:
    st.balloons()
    st.markdown(
        f"""
        <div class="level-up-box">
        🎉 恭喜升级！你的 AI 运动电子宠物已经达到 Lv {st.session_state.level}！<br>
        哼……虽然本宠物才没有特别开心，但你真的变强了一点点！
        </div>
        """,
        unsafe_allow_html=True
    )
    st.session_state.just_leveled_up = False

st.divider()

sport_text = st.text_area(
    "📝 今天做了什么运动？感觉怎么样？",
    placeholder="例如：跑了3公里，出了很多汗，很爽！",
    height=150
)

submit = st.button("🍖 喂养宠物（提交打卡）")


# =========================
# 提交处理
# =========================
if submit:
    if not sport_text.strip():
        st.warning("⚠️ 你还没有填写运动内容哦，宠物现在饿着肚子，不知道该吃什么经验值。")
    else:
        with st.spinner("🐾 宠物正在读取你的运动能量..."):
            try:
                result = call_ai_pet(sport_text)

                reply_text = result["reply_text"]
                exp_reward = result["exp_reward"]

                leveled_up = add_exp(exp_reward)

                st.session_state.total_checkins += 1
                st.session_state.last_reply = reply_text
                st.session_state.last_reward = exp_reward

                if leveled_up:
                    st.session_state.just_leveled_up = True
                    st.session_state.last_level = st.session_state.level

                st.success(f"✅ 打卡成功！本次获得：+{exp_reward} EXP")

                st.markdown(
                    f"""
                    <div class="reply-box">
                        <b>🐾 宠物回复：</b><br>
                        {reply_text}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.rerun()

            except json.JSONDecodeError:
                st.error("❌ 模型返回内容不是合法 JSON，请稍后重试。")

            except RuntimeError as e:
                st.error(f"❌ 配置错误：{e}")

            except Exception as e:
                st.error("❌ 请求 DeepSeek 模型失败，请检查 API Key、网络连接或账户余额。")
                with st.expander("查看错误详情"):
                    st.code(str(e))


# =========================
# 最近一次宠物回复
# =========================
if st.session_state.last_reply:
    st.markdown("### 💬 最近一次宠物留言")

    st.markdown(
        f"""
        <div class="reply-box">
            <b>🎁 上次奖励：</b> +{st.session_state.last_reward} EXP<br><br>
            {st.session_state.last_reply}
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================
# 页脚
# =========================
st.divider()

st.caption("🏋️ 坚持运动不是为了打败别人，而是为了喂养那个更强大的自己。")
