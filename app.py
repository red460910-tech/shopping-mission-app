import streamlit as st
import pandas as pd
import io
import requests
from PIL import Image, ImageDraw, ImageFont

# -----------------------------
# 기본 설정 및 세션 상태 초기화
# -----------------------------
st.set_page_config(page_title="중학생 장보기 미션 앱", page_icon="🛒", layout="wide")

MISSIONS = {
    "카레 만들기": {"budget": 20000, "desc": "맛있는 카레를 만들기 위해 필요한 재료를 알뜰하게 구매해 보세요!"},
    "여름캠핑 준비하기": {"budget": 45000, "desc": "친구들과 즐거운 캠핑을 떠나기 위한 준비물을 챙겨보세요!"},
    "친구 생일파티 준비하기": {"budget": 35000, "desc": "친구의 생일을 특별하게 만들어 줄 파티 용품과 간식을 골라보세요!"}
}

if "step" not in st.session_state:
    st.session_state.step = "start"  # start -> shopping -> result
if "selected_mission" not in st.session_state:
    st.session_state.selected_mission = None
if "budget" not in st.session_state:
    st.session_state.budget = 0
if "cart" not in st.session_state:
    st.session_state.cart = {}  # {품명: {'price': int, 'qty': int, 'img_url': str}}
if "quantities" not in st.session_state:
    st.session_state.quantities = {}

@st.cache_data
def load_products():
    try:
        df = pd.read_csv("products.csv")
        df["가격"] = pd.to_numeric(df["가격"], errors="coerce").fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"products.csv 파일을 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame(columns=["품명", "가격", "이미지 url"])

products_df = load_products()

# -----------------------------
# 영수증 카드 이미지 생성 함수 (Pillow)
# -----------------------------
def generate_result_image(mission_title, cart_items, total_spent, remaining_budget, reason_text):
    card_width = 800
    # 항목 수와 텍스트 길이에 따라 높이 동적 계산
    line_count = len(cart_items)
    base_height = 480 + (line_count * 45) + (len(reason_text) // 30 * 25)
    card_height = max(700, base_height)

    img = Image.new("RGB", (card_width, card_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 폰트 로드 시도 (서버 환경별 기본 폰트 대체 fallback)
    try:
        font_title = ImageFont.truetype("NanumGothicBold.ttf", 26)
        font_sub = ImageFont.truetype("NanumGothicBold.ttf", 18)
        font_body = ImageFont.truetype("NanumGothic.ttf", 15)
        font_small = ImageFont.truetype("NanumGothic.ttf", 13)
    except:
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_body = font_title
        font_small = font_title

    # 상단 헤더 박스
    draw.rectangle([(0, 0), (card_width, 90)], fill=(41, 128, 185))
    draw.text((30, 28), f"미션 : {mission_title} 구매 보고서", fill=(255, 255, 255), font=font_title)

    # 예산 요약 영역
    draw.rectangle([(30, 110), (card_width - 30, 190)], fill=(245, 247, 250), outline=(220, 224, 230))
    summary_text = f"총 사용 금액: {total_spent:,}원   |   남은 예산: {remaining_budget:,}원   (총 예산: {total_spent + remaining_budget:,}원)"
    draw.text((50, 138), summary_text, fill=(33, 37, 41), font=font_sub)

    # 구매 목록 테이블 헤더
    y_pos = 215
    draw.line([(30, y_pos), (card_width - 30, y_pos)], fill=(180, 180, 180), width=2)
    y_pos += 10
    draw.text((50, y_pos), "상품명", fill=(100, 100, 100), font=font_sub)
    draw.text((450, y_pos), "수량", fill=(100, 100, 100), font=font_sub)
    draw.text((580, y_pos), "금액", fill=(100, 100, 100), font=font_sub)
    y_pos += 30
    draw.line([(30, y_pos), (card_width - 30, y_pos)], fill=(220, 220, 220), width=1)

    # 구매 품목 나열
    y_pos += 15
    for name, item in cart_items.items():
        subtotal = item['price'] * item['qty']
        draw.text((50, y_pos), f"• {name}", fill=(30, 30, 30), font=font_body)
        draw.text((465, y_pos), f"{item['qty']}개", fill=(30, 30, 30), font=font_body)
        draw.text((580, y_pos), f"{subtotal:,}원", fill=(30, 30, 30), font=font_body)
        y_pos += 35

    # 구매 사유 영역
    y_pos += 20
    draw.rectangle([(30, y_pos), (card_width - 30, y_pos + 40)], fill=(235, 243, 250))
    draw.text((45, y_pos + 10), "■ 구매 이유 및 알뜰 소비 전략", fill=(41, 128, 185), font=font_sub)
    y_pos += 55

    # 텍스트 줄바꿈 처리
    wrapped_lines = []
    line_buf = ""
    for char in reason_text:
        line_buf += char
        if len(line_buf) >= 42 or char == "\n":
            wrapped_lines.append(line_buf.strip())
            line_buf = ""
    if line_buf:
        wrapped_lines.append(line_buf.strip())

    for r_line in wrapped_lines:
        draw.text((50, y_pos), r_line, fill=(50, 50, 50), font=font_body)
        y_pos += 25

    # 하단 푸터
    draw.line([(30, card_height - 50), (card_width - 30, card_height - 50)], fill=(220, 220, 220), width=1)
    draw.text((50, card_height - 35), "중학교 기술·가정 / 정보과 융합 디지털 장보기 실습 결과물", fill=(150, 150, 150), font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# -----------------------------
# 1. 시작 화면
# -----------------------------
if st.session_state.step == "start":
    st.title("🛒 중학생 알뜰 장보기 미션")
    st.markdown("도전할 미션을 선택하고 정해진 예산 안에서 합리적인 소비 계획을 세워보세요!")
    st.divider()

    col1, col2, col3 = st.columns(3)
    mission_keys = list(MISSIONS.keys())

    for i, col in enumerate([col1, col2, col3]):
        m_name = mission_keys[i]
        m_info = MISSIONS[m_name]
        with col:
            st.subheader(f"📌 {m_name}")
            st.info(f"**부여 예산:** {m_info['budget']:,}원")
            st.write(m_info["desc"])
            if st.button(f"'{m_name}' 도전하기", key=f"btn_{i}", use_container_width=True):
                st.session_state.selected_mission = m_name
                st.session_state.budget = m_info["budget"]
                st.session_state.cart = {}
                st.session_state.quantities = {row["품명"]: 0 for _, row in products_df.iterrows()}
                st.session_state.step = "shopping"
                st.rerun()

# -----------------------------
# 2. 쇼핑 화면
# -----------------------------
elif st.session_state.step == "shopping":
    st.subheader(f"🎯 미션: {st.session_state.selected_mission}")
    st.caption(f"총 부여 예산: **{st.session_state.budget:,}원**")
    st.divider()

    # 상단 안내 바
    current_spent = sum(item["price"] * item["qty"] for item in st.session_state.cart.values())
    remaining = st.session_state.budget - current_spent

    # 상품 진열 그리드 (3열)
    st.markdown("### 🛍️ 상품 진열대")
    cols = st.columns(3)

    for index, row in products_df.iterrows():
        p_name = row["품명"]
        p_price = int(row["가격"])
        p_img = str(row["이미지 url"]).strip()

        if p_name not in st.session_state.quantities:
            st.session_state.quantities[p_name] = 0

        with cols[index % 3]:
            st.container(border=True)
            with st.container(border=True):
                if p_img.startswith("http"):
                    st.image(p_img, use_container_width=True)
                else:
                    st.image("https://via.placeholder.com/300x200?text=No+Image", use_container_width=True)
                
                st.markdown(f"**{p_name}**")
                st.markdown(f"💰 `{p_price:,}원`")

                # 수량 조절 버튼
                btn_c1, btn_c2, btn_c3 = st.columns([1, 1.2, 1])
                with btn_c1:
                    if st.button("➖", key=f"minus_{p_name}"):
                        if st.session_state.quantities[p_name] > 0:
                            st.session_state.quantities[p_name] -= 1
                            st.rerun()
                with btn_c2:
                    st.markdown(f"<p style='text-align: center; margin-top: 5px;'><b>{st.session_state.quantities[p_name]}개</b></p>", unsafe_allow_html=True)
                with btn_c3:
                    if st.button("➕", key=f"plus_{p_name}"):
                        st.session_state.quantities[p_name] += 1
                        st.rerun()

                # 장바구니 담기 버튼
                if st.button("🛒 장바구니 담기", key=f"add_{p_name}", use_container_width=True):
                    qty = st.session_state.quantities[p_name]
                    if qty > 0:
                        st.session_state.cart[p_name] = {
                            "price": p_price,
                            "qty": qty,
                            "img_url": p_img
                        }
                        st.success(f"{p_name} {qty}개가 장바구니에 담겼습니다!")
                    else:
                        if p_name in st.session_state.cart:
                            del st.session_state.cart[p_name]
                    st.rerun()

    st.divider()

    # 하단 장바구니 및 예산 계산 섹션
    st.markdown("### 🛒 내 장바구니 현황")
    
    cart_col1, cart_col2 = st.columns([2, 1])

    with cart_col1:
        if not st.session_state.cart:
            st.info("장바구니가 비어 있습니다. 위 진열대에서 물건을 골라 담아보세요.")
        else:
            cart_table_data = []
            for name, item in st.session_state.cart.items():
                cart_table_data.append({
                    "품명": name,
                    "단가": f"{item['price']:,}원",
                    "수량": f"{item['qty']}개",
                    "합계": f"{(item['price'] * item['qty']):,}원"
                })
            st.dataframe(pd.DataFrame(cart_table_data), use_container_width=True, hide_index=True)

    with cart_col2:
        st.markdown(f"**총 예산:** {st.session_state.budget:,}원")
        st.markdown(f"**현재 구매 총액:** `{current_spent:,}원`")
        
        if remaining >= 0:
            st.metric(label="남은 예산", value=f"{remaining:,}원")
        else:
            st.metric(label="예산 초과", value=f"{abs(remaining):,}원 초과", delta=f"{remaining:,}원", delta_color="inverse")
            st.error("⚠️ 예산을 초과했습니다! 수량을 조절해 주세요.")

        # 제출 조건 검사
        is_over_budget = remaining < 0
        is_empty_cart = len(st.session_state.cart) == 0
        submit_disabled = is_over_budget or is_empty_cart

        if st.button("✅ 최종 제출하기", type="primary", disabled=submit_disabled, use_container_width=True):
            st.session_state.step = "result"
            st.rerun()

# -----------------------------
# 3. 결과 화면
# -----------------------------
elif st.session_state.step == "result":
    mission_title = st.session_state.selected_mission
    total_spent = sum(item["price"] * item["qty"] for item in st.session_state.cart.values())
    remaining = st.session_state.budget - total_spent

    st.title("🎉 장보기 미션 완료 보고서")
    st.subheader(f"미션: {mission_title}")
    st.divider()

    # 금액 요약
    sum_c1, sum_c2, sum_c3 = st.columns(3)
    sum_c1.metric("총 예산", f"{st.session_state.budget:,}원")
    sum_c2.metric("사용한 금액", f"{total_spent:,}원")
    sum_c3.metric("남은 잔액", f"{remaining:,}원")

    st.markdown("### 📋 최종 구매 물품")
    res_cols = st.columns(min(len(st.session_state.cart), 4) if st.session_state.cart else 1)
    
    for idx, (name, item) in enumerate(st.session_state.cart.items()):
        col_target = res_cols[idx % len(res_cols)]
        with col_target:
            with st.container(border=True):
                if item["img_url"].startswith("http"):
                    st.image(item["img_url"], use_container_width=True)
                st.markdown(f"**{name}**")
                st.caption(f"{item['qty']}개 / {(item['price'] * item['qty']):,}원")

    st.divider()

    # 구매 이유 입력창
    st.markdown("### ✍️ 구매 이유 및 알뜰 전략 작성")
    reason = st.text_area(
        "선택한 물건들을 고른 이유와 예산에 맞추기 위해 세운 전략을 자세히 적어주세요:",
        placeholder="예) 카레의 주재료인 감자와 고기를 우선 담고, 남은 예산에 맞춰 양파와 당근의 수량을 알맞게 조절하여 구매했습니다.",
        height=130
    )

    if reason.strip():
        # 이미지 생성 및 다운로드 제공
        img_bytes = generate_result_image(
            mission_title=mission_title,
            cart_items=st.session_state.cart,
            total_spent=total_spent,
            remaining_budget=remaining,
            reason_text=reason
        )

        st.download_button(
            label="🖼️ 결과 보고서 그림으로 저장 (PNG 다운로드)",
            data=img_bytes,
            file_name=f"장보기결과_{mission_title.replace(' ', '_')}.png",
            mime="image/png",
            type="primary"
        )
    else:
        st.warning("구매 이유를 입력하시면 보고서 이미지 다운로드 버튼이 활성화됩니다.")

    if st.button("🔄 처음으로 돌아가기 (다시 하기)"):
        st.session_state.step = "start"
        st.session_state.cart = {}
        st.rerun()
