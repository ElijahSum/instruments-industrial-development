import os
from datetime import time

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from dashboard_shared import CSV_COLUMNS, DATETIME_FORMAT

REQUEST_TIMEOUT = float(os.getenv("API_TIMEOUT", "15"))


def get_api_url() -> str:
    """Read the backend API URL from Streamlit secrets or env vars."""
    try:
        secret_url = st.secrets.get("API_URL")
    except StreamlitSecretNotFoundError:
        secret_url = None

    if secret_url:
        return str(secret_url).rstrip("/")
    return os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")


API_URL = get_api_url()

st.set_page_config(page_title="Energy Dashboard", layout="wide")


def parse_api_error(api_response: requests.Response) -> str:
    """Extract a readable error message from an API response."""
    try:
        error_payload = api_response.json()
    except ValueError:
        return api_response.text.strip() or f"HTTP {api_response.status_code}"

    detail = error_payload.get("detail")
    if isinstance(detail, str) and detail.strip():
        return detail
    return f"HTTP {api_response.status_code}"


def fetch_records() -> pd.DataFrame:
    """Load records from the backend API."""
    api_response = requests.get(f"{API_URL}/records", timeout=REQUEST_TIMEOUT)
    api_response.raise_for_status()

    dataframe = pd.DataFrame(api_response.json())
    if dataframe.empty:
        return pd.DataFrame(columns=CSV_COLUMNS)

    dataframe["timestep"] = pd.to_datetime(
        dataframe["timestep"], format=DATETIME_FORMAT
    )
    return dataframe.sort_values("timestep").reset_index(drop=True)


def add_record(payload_data: dict) -> requests.Response:
    """Send a record-creation request to the backend."""
    return requests.post(
        f"{API_URL}/records",
        json=payload_data,
        timeout=REQUEST_TIMEOUT,
    )


def delete_record(target_record_id: int) -> requests.Response:
    """Send a record-deletion request to the backend."""
    return requests.delete(
        f"{API_URL}/records/{target_record_id}",
        timeout=REQUEST_TIMEOUT,
    )


def render_consumption_chart(records_df: pd.DataFrame) -> None:
    """Render the consumption time-series chart."""
    consumption = records_df.melt(
        id_vars=["timestep"],
        value_vars=["consumption_eur", "consumption_sib"],
        var_name="region",
        value_name="value",
    )
    figure = px.line(
        consumption,
        x="timestep",
        y="value",
        color="region",
        title="Потребление энергии по времени",
        labels={
            "timestep": "Время",
            "value": "Потребление",
            "region": "Показатель",
        },
    )
    st.plotly_chart(figure, use_container_width=True)


def render_price_chart(records_df: pd.DataFrame) -> None:
    """Render the price time-series chart."""
    prices = records_df.melt(
        id_vars=["timestep"],
        value_vars=["price_eur", "price_sib"],
        var_name="region",
        value_name="value",
    )
    figure = px.line(
        prices,
        x="timestep",
        y="value",
        color="region",
        title="Цены по времени",
        labels={
            "timestep": "Время",
            "value": "Цена",
            "region": "Показатель",
        },
    )
    st.plotly_chart(figure, use_container_width=True)


def show_feedback() -> None:
    """Show success or error messages stored in the session state."""
    if message := st.session_state.pop("success_message", None):
        st.success(message)
    if message := st.session_state.pop("error_message", None):
        st.error(message)


st.title("Мини-дашборд рынка электроэнергии")
st.caption(f"Данные загружаются только через FastAPI: `{API_URL}`")
show_feedback()

toolbar_col, stats_col = st.columns([1, 3])
with toolbar_col:
    if st.button("Обновить данные", use_container_width=True):
        st.rerun()

try:
    data = fetch_records()
except requests.RequestException as exc:
    response = getattr(exc, "response", None)
    if response is not None:
        st.error(parse_api_error(response))
    else:
        st.error(f"Не удалось подключиться к API: {exc}")
    st.stop()

with stats_col:
    total_rows = len(data)
    timestep_range = (
        "Нет данных"
        if data.empty
        else (
            f"{data['timestep'].min():%Y-%m-%d %H:%M} - "
            f"{data['timestep'].max():%Y-%m-%d %H:%M}"
        )
    )
    st.write(f"Записей: **{total_rows}**")
    st.write(f"Диапазон данных: **{timestep_range}**")

st.subheader("Таблица записей")
table_data = data.copy()
if not table_data.empty:
    table_data["timestep"] = table_data["timestep"].dt.strftime(
        DATETIME_FORMAT
    )
st.dataframe(table_data, use_container_width=True, hide_index=True)

if not data.empty:
    left_chart, right_chart = st.columns(2)
    with left_chart:
        render_consumption_chart(data)
    with right_chart:
        render_price_chart(data)
else:
    st.info("В API пока нет записей для отображения.")

st.subheader("Добавление записи")
with st.form("add_record_form"):
    form_left, form_right = st.columns(2)
    with form_left:
        date_value = st.date_input("Дата")
        time_value = st.time_input("Время", value=time(0, 0), step=3600)
        consumption_eur = st.number_input(
            "Потребление EUR", min_value=0.0, format="%.2f"
        )
    with form_right:
        consumption_sib = st.number_input(
            "Потребление SIB", min_value=0.0, format="%.2f"
        )
        price_eur = st.number_input("Цена EUR", min_value=0.0, format="%.2f")
        price_sib = st.number_input("Цена SIB", min_value=0.0, format="%.2f")

    submit_add = st.form_submit_button(
        "Добавить запись",
        use_container_width=True,
    )

    if submit_add:
        new_record_payload = {
            "timestep": f"{date_value:%Y-%m-%d} {time_value:%H:%M}",
            "consumption_eur": consumption_eur,
            "consumption_sib": consumption_sib,
            "price_eur": price_eur,
            "price_sib": price_sib,
        }
        try:
            create_response = add_record(new_record_payload)
        except requests.RequestException as exc:
            st.session_state["error_message"] = (
                f"Не удалось выполнить POST-запрос: {exc}"
            )
            st.rerun()

        if create_response.status_code == 201:
            created = create_response.json()
            st.session_state["success_message"] = (
                f"Запись id={created['id']} успешно добавлена."
            )
            st.rerun()

        st.session_state["error_message"] = parse_api_error(create_response)
        st.rerun()

st.subheader("Удаление записи")
available_ids = [] if data.empty else data["id"].astype(int).tolist()
help_text = (
    "Доступные id: нет записей."
    if not available_ids
    else f"Примеры доступных id: {', '.join(map(str, available_ids[:10]))}"
)

with st.form("delete_record_form"):
    default_id = 1 if not available_ids else int(available_ids[-1])
    record_id = st.number_input(
        "ID записи для удаления",
        min_value=1,
        step=1,
        value=default_id,
        help=help_text,
        disabled=not available_ids,
    )
    submit_delete = st.form_submit_button(
        "Удалить запись",
        use_container_width=True,
        disabled=not available_ids,
    )

    if submit_delete:
        try:
            delete_response = delete_record(int(record_id))
        except requests.RequestException as exc:
            st.session_state["error_message"] = (
                f"Не удалось выполнить DELETE-запрос: {exc}"
            )
            st.rerun()

        if delete_response.ok:
            st.session_state["success_message"] = (
                f"Запись id={int(record_id)} успешно удалена."
            )
            st.rerun()

        st.session_state["error_message"] = parse_api_error(delete_response)
        st.rerun()
