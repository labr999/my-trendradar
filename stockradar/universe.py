from __future__ import annotations

import requests


TWSE_URL = (
    "https://openapi.twse.com.tw/"
    "v1/opendata/t187ap03_L"
)


TPEX_URL = (
    "https://www.tpex.org.tw/"
    "openapi/v1/mopsfin_t187ap03_O"
)


def get_twse_stocks() -> list[dict]:
    """
    取得台灣證券交易所上市股票。
    """

    response = requests.get(
        TWSE_URL,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    result = []

    for item in data:

        code = str(
            item.get(
                "公司代號",
                ""
            )
        ).strip()

        name = str(
            item.get(
                "公司名稱",
                ""
            )
        ).strip()

        if (
            code.isdigit()
            and len(code) == 4
        ):

            result.append(
                {
                    "symbol": code,
                    "name": name,
                    "market": "TW",
                }
            )

    return result


def get_tpex_stocks() -> list[dict]:
    """
    取得台灣證券櫃檯買賣中心股票。

    如果 TPEx API 暫時無法取得，
    不讓整個 TrendRadar 停止。
    """

    try:

        response = requests.get(
            TPEX_URL,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"TPEx股票池取得失敗：{exc}"
        )

        return []

    result = []

    for item in data:

        code = str(
            item.get(
                "SecuritiesCompanyCode",
                item.get(
                    "公司代號",
                    ""
                )
            )
        ).strip()

        name = str(
            item.get(
                "CompanyName",
                item.get(
                    "公司名稱",
                    ""
                )
            )
        ).strip()

        if (
            code.isdigit()
            and len(code) == 4
        ):

            result.append(
                {
                    "symbol": code,
                    "name": name,
                    "market": "TWO",
                }
            )

    return result


def get_universe() -> list[dict]:
    """
    建立 TrendRadar 全市場股票池。

    TWSE + TPEx
    """

    stocks = []

    # -------------------------
    # TWSE
    # -------------------------

    try:

        stocks.extend(
            get_twse_stocks()
        )

    except Exception as exc:

        print(
            f"TWSE股票池取得失敗：{exc}"
        )

    # -------------------------
    # TPEx
    # -------------------------

    stocks.extend(
        get_tpex_stocks()
    )

    # -------------------------
    # 去除重複股票
    # -------------------------

    unique = {}

    for stock in stocks:

        symbol = stock[
            "symbol"
        ]

        unique[symbol] = stock

    # -------------------------
    # 依股票代號排序
    # -------------------------

    result = sorted(
        unique.values(),
        key=lambda x:
            x["symbol"]
    )

    print(
        f"全市場股票池："
        f"{len(result)} 檔"
    )

    return result
