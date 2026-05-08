# app.py
# -*- coding: utf-8 -*-

import json
import re
import streamlit as st
from openai import OpenAI


# =========================
# 页面基础配置
# =========================
st.set_page_config(
    page_title="AI 运动电子宠物",
    page_icon="🏃",
    layout="centered"
)


# =========================
# 自定义 CSS 美化
# =========================
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 900;
        text-align: center;
        padding: 18px 10px;
        margin-bottom: 10px;
        border-radius: 22px;
        background: linear-gradient(135deg, #1f2937, #111827);
        color: #ffffff;
        box-shadow: 0 10px 30px rgba(0,0,0,0.18);
    }

    .pet-card {
        padding: 22px;
        border-radius: 22px;
        background: linear-gradient(135deg, #fff7ed, #ecfeff);
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 10px 28px rgba(0,0,0,0.08);
        margin-bottom: 18px;
    }

    .pet-name {
        font-size: 1.35rem;
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
    }

    .small-tip {
        color: #6b7280;
        font-size: 0.92rem;
    }

    .stButton button {
        width: 100%;
        border-radius: 14px;
        height: 3rem;
        font-size: 1.05rem;
        font-weight: 700;
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

if "last_reply" not in st.session_state:
    st.session_state.last_reply = ""

if "total_checkins" not in st.session_state:
    st.session_state.total_checkins = 0


# =========================
# 工具函数
# =========================
def extract_json_from_text(text: str) -> dict:
    """
    尽量从模型输出中提取 JSON。
    兼容以下情况：
    1. 纯 JSON
    2. ```json ... ```
    3. 前后夹杂少量解释文本
    """
    if not text:
        raise ValueError("模型返回内容为空。")

    text = text.strip()

    # 去除 Markdown 代码块
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # 先直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 再尝试截取第一个 JSON 对象
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("无法从模型返回内容中解析 JSON。")


def normalize_exp_reward(value) -> int:
    """
    将模型返回的经验值转成 10~50 之间的整数。
    即使模型不听话，也在程序侧兜底。
    """
    try:
        exp = int(value)
    except Exception:
        exp = 10

    exp = max(10, min(50, exp))
    return exp


def call_ai_pet(api_key: str, base_url: str, model_name: str, sport_text: str) -> dict:
    """
    调用 OpenAI SDK 兼容接口，让大模型分析运动打卡内容。
    """
    client = OpenAI(
        api_key=api_key,
        base_url=base_url.strip() if base_url.strip() else None
    )

    system_prompt = """
你是一只“AI运动电子宠物”，性格傲娇但很会鼓励主人。
你的任务是分析用户今天的运动打卡内容。

请完成：
1. 提取用户的运动类型。
2. 判断运动强度，可为：低强度 / 中强度 / 高强度。
3. 用傲娇、可爱、鼓励的宠物口吻回复用户。
4. 根据运动情况给出 10 到 50 之间的整数经验值奖励。

你必须只返回 JSON，不要返回 Markdown，不要返回多余解释。

JSON 格式必须为：
{
  "reply_text": "你的宠物回复文本",
  "exp_reward": 30
}

注意：
- reply_text 里可以自然提到运动类型和运动强度。
- exp_reward 必须是 10 到 50 之间的整数。
- 如果用户内容很敷衍或不是运动，也要温柔提醒，并给较低经验值。
"""

    user_prompt = f"""
用户今天的运动打卡内容如下：
{sport_text}

请按照要求返回 JSON。
"""

    try:
        # 优先使用 JSON 模式。部分 OpenAI 兼容服务可能不支持 response_format。
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            response_format={"type": "json_object"}
        )
    except Exception:
        # 兼容不支持 response_format 的接口，例如某些第三方兼容服务
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8
        )

    content = response.choices[0].message.content
    data = extract_json_from_text(content)

    reply_text = str(data.get("reply_text", "")).strip()
    exp_reward = normalize_exp_reward(data.get("exp_reward", 10))

    if not reply_text:
        reply_text = "哼，虽然你写得有点简单，但本宠物还是感受到你努力运动的气息啦！继续坚持，不许偷懒！"

    return {
        "reply_text": reply_text,
        "exp_reward": exp_reward
    }


def add_exp(exp_reward: int) -> bool:
    """
    增加经验值。
    返回是否升级。
    经验值达到 100 后升级，并保留溢出的经验值。
    例如：当前 90，奖励 30 -> Lv +1，EXP 20。
    """
    leveled_up = False
    st.session_state.exp += exp_reward

    while st.session_state.exp >= 100:
        st.session_state.level += 1
        st.session_state.exp -= 100
        leveled_up = True

    return leveled_up


# =========================
# Sidebar
# =========================
with st.sidebar:
    st.header("🔐 模型接口设置")

    api_key = st.text_input(
        "请输入 API Key",
        type="password",
        placeholder="sk-..."
    )

    base_url = st.text_input(
        "Base URL",
        value="https://api.openai.com/v1",
        help="可填写 OpenAI 兼容接口，例如 DeepSeek、通义千问、智谱等平台的兼容地址。"
    )

    model_name = st.text_input(
        "模型名称",
        value="gpt-4o-mini",
        help="如果使用 DeepSeek，可改为 deepseek-chat；如果使用其他平台，请填写对应模型名。"
    )

    st.divider()

    st.caption("🐾 小提示")
    st.write(
        "本应用不会保存你的 API Key。刷新页面后需要重新输入。"
    )


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
        <div class="pet-name">🐣 当前宠物状态</div>
        <div>你的电子宠物正在盯着你：<b>“今天有没有好好运动呀？”</b></div>
    </div>
    """,
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("🌟 等级 Lv", st.session_state.level)

with col2:
    st.metric("⚡ 当前 EXP", f"{st.session_state.exp} / 100")

with col3:
    st.metric("📅 累计打卡", st.session_state.total_checkins)

st.progress(st.session_state.exp / 100)

st.markdown(
    '<p class="small-tip">经验值达到 100 后，宠物会升级，并触发庆祝特效 🎉</p>',
    unsafe_allow_html=True
)

st.divider()

sport_text = st.text_area(
    "📝 运动打卡内容",
    placeholder="今天做了什么运动？感觉怎么样？（例如：跑了3公里，出了很多汗，很爽！）",
    height=140
)

submit = st.button("🍖 喂养宠物（提交打卡）")


# =========================
# 提交逻辑
# =========================
if submit:
    if not api_key.strip():
        st.warning("⚠️ 请先在左侧输入 API Key，本宠物现在还没有能量连接大模型喵。")
    elif not base_url.strip():
        st.warning("⚠️ 请填写 Base URL，例如：https://api.openai.com/v1")
    elif not model_name.strip():
        st.warning("⚠️ 请填写模型名称，例如：gpt-4o-mini 或 deepseek-chat")
    elif not sport_text.strip():
        st.warning("⚠️ 你还没有填写今天的运动内容哦，宠物不知道该吃什么经验值。")
    else:
        with st.spinner("🐾 宠物正在认真嗅探你的运动能量，请稍等..."):
            try:
                result = call_ai_pet(
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name,
                    sport_text=sport_text
                )

                reply_text = result["reply_text"]
                exp_reward = result["exp_reward"]

                leveled_up = add_exp(exp_reward)
                st.session_state.total_checkins += 1
                st.session_state.last_reply = reply_text

                st.success(f"✅ 打卡成功！本次获得经验值：+{exp_reward} EXP")

                st.markdown(
                    f"""
                    <div class="reply-box">
                        <b>🐾 宠物回复：</b><br>
                        {reply_text}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if leveled_up:
                    st.balloons()
                    st.success(
                        f"🎉 恭喜！你的 AI 运动电子宠物升级啦！当前等级：Lv {st.session_state.level}"
                    )

                st.rerun()

            except json.JSONDecodeError:
                st.error("❌ 模型返回的内容不是合法 JSON。请换一个模型，或稍后重试。")
            except ValueError as e:
                st.error(f"❌ 解析失败：{e}")
            except Exception as e:
                st.error("❌ 请求大模型失败，请检查 API Key、Base URL、模型名称或网络连接。")
                with st.expander("查看错误详情"):
                    st.code(str(e))


# =========================
# 展示上一次回复
# =========================
if st.session_state.last_reply:
    st.markdown("### 💬 最近一次宠物留言")
    st.markdown(
        f"""
        <div class="reply-box">
            {st.session_state.last_reply}
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================
# 页脚
# =========================
st.divider()
st.caption("🏋️ 坚持运动不是为了打败别人，而是为了喂饱那个更强大的自己。")