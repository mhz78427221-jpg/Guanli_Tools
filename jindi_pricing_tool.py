import streamlit as st
import pandas as pd
from openai import OpenAI
import httpx
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================== 0. 权限与身份配置 ==================
USER_CREDENTIALS = {
    "admin": "mahaozhe",
    "jindi": "jindi666",
    "peipei": "persely2020"
}

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["current_user"] = None

if not st.session_state["authenticated"]:
    st.set_page_config(page_title="观梨生物 - 内部系统登录", layout="centered")
    st.markdown("<h2 style='text-align: center;'>🛡️ 观梨生物内部指挥系统</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("工号")
            password = st.text_input("密码", type="password")
            if st.form_submit_button("安全登录", use_container_width=True):
                if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
                    st.session_state["authenticated"] = True
                    st.session_state["current_user"] = username
                    st.rerun()
                else:
                    st.error("❌ 口令错误")
    st.stop()

# ================== 1. 核心精算参数 ==================
DEEPSEEK_API_KEY = "sk-2046afe4f5ed4d6b843c2a7654c6e2ee"

FIXED_LOGISTICS = 3.85      # 物流费 (元)
FIXED_PLATFORM_FEE = 0.05/1.06   # 平台扣点 (5%)
FIXED_LOSS_RATE = 0.03      # ⚠️ 修正：货损基于成本 (3%)
FIXED_TAX_POINT = 0.06/1.06      # 佣金税点 (6%)
DB_FILE = "guanli_product_db.csv"

def load_database():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame({"产品名称": ["三修精华正装 30ml"], "最新料体成本_元": [15.0]})
        df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    return dict(zip(pd.read_csv(DB_FILE, encoding='utf-8-sig')["产品名称"], 
                    pd.read_csv(DB_FILE, encoding='utf-8-sig')["最新料体成本_元"]))

PRODUCT_DB = load_database()

# ================== 2. 主页面 UI ==================
st.set_page_config(page_title="观梨生物 - 精算中控台", layout="wide")

with st.sidebar:
    st.markdown(f"### 👤 在线: **{st.session_state['current_user'].upper()}**")
    if st.button("🚪 登出"):
        st.session_state["authenticated"] = False
        st.rerun()

st.title("🧮 观梨直播机制核算与验证台 7.0")
st.caption(f"🟢 数据库连接正常 | 成本底座支持：朱珮珮")

mode = st.radio("模式选择：", ["🎯 价格逆推", "🔍 利润验证"], horizontal=True)
st.divider()

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🛒 选品组合")
    selected_prods = st.multiselect("调取库文件：", options=list(PRODUCT_DB.keys()))
    
    total_raw_cost = 0.0
    combo_items = []
    if selected_prods:
        for p in selected_prods:
            c1, c2 = st.columns([3, 1])
            with c1: st.write(f"🔹 {p}")
            with c2: qty = st.number_input(f"数量##{p}", min_value=1, value=1, label_visibility="collapsed")
            total_raw_cost += PRODUCT_DB[p] * qty
            combo_items.append(f"{p} x{qty}")
        
        # 核心逻辑变更显示
        loss_amount = total_raw_cost * FIXED_LOSS_RATE
        total_with_loss = total_raw_cost + loss_amount
        st.info(f"**成本明细：**\n- 纯料体成本：¥{total_raw_cost:.2f}\n- 3%货损(朱珮珮预设)：¥{loss_amount:.2f}\n- **综合料体总额：¥{total_with_loss:.2f}**")

    st.divider()
    st.subheader("⚙️ 业务变量")
    comm_rate = st.number_input("达人佣金 (%)", value=25.0)
    if mode == "🎯 价格逆推":
        target_m = st.number_input("期望纯利润率 (%)", value=25.0)
    else:
        test_p = st.number_input("拟定直播间售价 (元)", value=178.0)

    calc = st.button("🚀 执行精算", type="primary", use_container_width=True)

with col_r:
    if calc and selected_prods:
        # 新逻辑：分子包含货损
        total_numerator = total_with_loss + FIXED_LOGISTICS
        # 分母不再包含货损率
        total_denominator_rate = (comm_rate/100) + FIXED_PLATFORM_FEE + FIXED_TAX_POINT

        if mode == "🎯 价格逆推":
            final_rate = total_denominator_rate + (target_m/100)
            if final_rate >= 1:
                st.error("🚨 费率击穿！")
            else:
                final_p = total_numerator / (1 - final_rate)
                st.metric("建议售价", f"¥ {final_p:.2f}")
                real_m = target_m
        else:
            # 利润验证新逻辑
            real_profit = test_p * (1 - total_denominator_rate) - total_numerator
            real_m = (real_profit / test_p) * 100
            
            st.subheader("📈 验证结果")
            m1, m2 = st.columns(2)
            m1.metric("单单净利额", f"¥ {real_profit:.2f}")
            m2.metric("最终净利润率", f"{real_m:.2f}%")
            
            if real_m < 15: st.error("⚠️ 利润红线告警")
            elif real_m > 25: st.success("✅ 高利润模型")

        # AI 种草引擎同步更新
        st.divider()
        st.subheader("✍️ AI 首席种草官")
        prompt = f"""
        你是观梨爆文操盘手。针对油敏肌/脂皮人群，为货盘【{" + ".join(combo_items)}】写一篇种草文案。
        要求：
        1. 标题带Emoji，直击泛红烂脸痛点。
        2. 文案要感性，通过描述一到下午就脸烫、用什么都过敏的场景引发共鸣。
        3. 植入组合用法，强调正装+小样的囤货价值。
        4. 绝对禁止提利润、佣金、成本等内部词汇。
        """
        try:
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", http_client=httpx.Client(verify=False))
            resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            st.markdown(resp.choices[0].message.content)
        except:
            st.warning("AI 信号波段异常")