import yfinance as yf
import pandas as pd
import cbrapi as cbr
from scipy.optimize import minimize
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import TimeSeriesSplit, cross_validate


# ==========================================
# ПОЗИЦИЯ 8: ФОРМУЛЫ
# ==========================================
def apt_expected_return(risk_free_rate, betas, factor_premiums, eps=0):
    """
    Расчет ожидаемой доходности по многофакторной модели APT.
    betas: список чувствительностей [beta_imoex, beta_rub, beta_oil]
    factor_premiums: список премий за риск [imoex, rub, oil]
    """
    # Суммируем произведения каждой беты на соответствующую премию фактора
    total_factor_contribution = sum(b * p for b, p in zip(betas, factor_premiums)) + eps
    return risk_free_rate + total_factor_contribution


def neg_sharpe(weights, expected_returns, cov_matrix, rf_rate):
    """Отрицательный коэффициент Шарпа (для минимизации)"""
    port_ret = np.sum(weights * expected_returns)
    port_vol = np.sqrt(weights @ cov_matrix @ weights)
    sharpe = (port_ret - rf_rate) / port_vol
    return -sharpe


# ==========================================
# ПОЗИЦИЯ 9: СКАЧИВАНИЕ ДАННЫХ
# ==========================================

def normalize_date_index(idx):
    """Приводит индекс к pandas DatetimeIndex без времени и временной зоны."""
    if isinstance(idx, pd.PeriodIndex):
        idx = idx.to_timestamp()
    return pd.to_datetime(idx).tz_localize(None).normalize()


# Определяем функцию download_stock, которая скачивает данные одной акции
# и сохраняет их в CSV-файл
# Параметры функции:
#   ticker (str)      - биржевой тикер компании (например, 'AFLT.ME' для Аэрофлота)
#   filename (str)    - имя файла, в который будут сохранены данные
#   start_date (str)  - начальная дата в формате
#   end_date (str)    - конечная дата в формате
def download_stock(ticker, filename, start_date, end_date):
    """
    Функция для скачивания исторических цен акции и сохранения в CSV файл.
    """
    # Выводим сообщение в консоль о начале загрузки текущего тикера.
    # Это нужно для отслеживания прогресса выполнения программы.
    print(f"Загружаю данные для {ticker}...")

    # Основная команда: yf.download() - отправляет запрос к API Yahoo Finance [citation:1][citation:6].
    # Параметры:
    #   ticker     - код ценной бумаги (например, 'AFLT.ME')
    #   start      - дата начала периода (включительно)
    #   end        - дата окончания периода (фактически данные идут до предыдущего дня)
    #   auto_adjust=False - отключаем автоматическую корректировку цен.
    #                       При auto_adjust=True цены автоматически корректируются
    #                       с учётом дивидендов и сплитов, а колонка Adj Close удаляется [citation:1].
    #                       Явно указываем False, чтобы получить и обычные, и скорректированные цены.
    #   progress=False   - отключаем вывод прогресс-бара в консоль для чистоты вывода
    #   timeout=30       - устанавливаем таймаут 30 секунд, чтобы избежать зависания
    data = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        # interval="1mo",
        auto_adjust=False,
        progress=False,
        timeout=30
    )

    # Сохраняем полученный DataFrame в CSV файл [citation:7][citation:9].
    # CSV файл будет содержать колонки: Date, Open, High, Low, Close, Adj Close, Volume
    # Date - это индекс (дата), остальные - цены и объём торгов.
    data.to_csv(filename)

    # Выводим сообщение об успешном завершении загрузки текущего тикера.
    print(f"Акция {ticker} сохранена в файл '{filename}' (записей: {len(data)})")
    return True


def download__factors(start_date, end_date):
    """
    Загружает макроэкономические факторы для модели APT.
    Возвращает DataFrame с дневными доходностями.
    """
    # 1. Определяем тикеры
    # Индекс МосБиржи
    imoex_ticker = "IMOEX.ME"
    # Курс рубля (сколько рублей стоит 1 доллар)
    ruble_ticker = "RUB=X"
    # Цена на нефть марки Brent (наиболее релевантный бенчмарк для РФ)
    oil_ticker = "BZ=F"

    tickers = [imoex_ticker, ruble_ticker, oil_ticker]
    print(f"Загрузка данных для тикеров: {tickers}...")

    # 2. Скачиваем исторические данные
    # yfinance скачает все тикеры разом и вернет мультииндексный DataFrame
    data = yf.download(tickers, start=start_date, end=end_date)

    # 3. Приводим данные в порядок
    # Нас интересуют только цены закрытия, чтобы рассчитать доходность
    close_prices = data['Close'].copy()

    # Переименовываем столбцы для удобства
    close_prices.columns = ['IMOEX', 'RUB_USD', 'BRENT']

    # Сохраняем данные индекса в CSV файл
    close_prices.to_csv("factors.csv")

    # Удаляем строки, где нет данных (выходные, пропуски)
    close_prices.dropna(inplace=True)

    # 4. Рассчитываем доходность
    returns = close_prices.pct_change().dropna()
    returns = returns.clip(lower=-0.2, upper=0.2)

    returns.index = normalize_date_index(returns.index)

    print(f"Готово! Загружено {len(returns)} дня.")
    print(returns.head())

    return returns


# Скачиваем индекс Ruonia
def download_ruonia(start_date, end_date):
    df = cbr.ruonia.get_ruonia_overnight(start_date, end_date, "D")
    df.index = normalize_date_index(df.index)
    df.to_csv('ruonia_overnight.csv', encoding='utf-8')
    return df


def load_stock_data(filename):
    """Загрузка данных акции и расчет доходности"""
    column_names = ['Date', 'Adj Close', 'Close', 'High', 'Low', 'Open', 'Volume']

    stock = pd.read_csv(
        filename,
        skiprows=3,
        header=None,
        names=column_names,
        index_col=0,
        parse_dates=True,
        date_format="%Y-%m-%d"
    )
    stock.index = normalize_date_index(stock.index)
    stock["Close"] = pd.to_numeric(stock["Close"], errors="coerce")
    stock["return"] = stock["Close"].pct_change().dropna()
    stock["return"] = stock["return"].clip(lower=-0.2, upper=0.2)

    return stock


# # ==========================================
# # ПОЗИЦИЯ 10: ЧИСТКА ДАННЫХ И МАШИННОЕ ОБУЧЕНИЕ
# # ==========================================
def regress_stock_on_factors(stock_returns, factor_returns, rf, n_splits=10):
    """
    Линейная регрессия доходности акции на факторы с кросс-валидацией.

    Параметры
    ----------
    stock_returns : pd.Series
        Дневные доходности акции.
    factor_returns : pd.DataFrame
        Дневные доходности факторов с колонками ['IMOEX', 'RUB_USD', 'BRENT'].
    cv_folds : int
        Количество фолдов для кросс-валидации (по умолчанию 5).

    Возвращает
    -------
    model : sklearn.linear_model.LinearRegression
        Модель, обученная на всех данных.
    metrics : dict
        Словарь с усреднёнными метриками кросс-валидации и коэффициентами финальной модели.
    """
    # Приводим индексы к единому формату и объединяем данные

    df = pd.concat([stock_returns.rename("stock"), factor_returns, rf], axis=1, join="inner")
    df.dropna(inplace=True)

    rf = rf.reindex(df.index).ffill()

    # Разделяем зависимую и независимые переменные
    y = df["stock"] - rf
    X = pd.DataFrame({
        "IMOEX": df["IMOEX"] - rf,
        "RUB_USD": df["RUB_USD"],
        "BRENT": df["BRENT"]
    })

    # Временной сплиттер: training size растёт, test всегда в будущем
    tscv = TimeSeriesSplit(n_splits=n_splits)

    scoring = {'R2': 'r2', 'MAE': 'neg_mean_absolute_error'}
    cv_results = cross_validate(
        LinearRegression(), X, y,
        cv=tscv,
        scoring=scoring
    )

    r2_mean = cv_results['test_R2'].mean()
    mae_mean = -cv_results['test_MAE'].mean()

    final_model = LinearRegression()
    final_model.fit(X, y)

    metrics = {
        'R2': r2_mean,
        'MAE': mae_mean,
        'R2_mean': r2_mean,
        'MAE_mean': mae_mean,
        'coefficients': dict(zip(['IMOEX', 'RUB_USD', 'BRENT'], final_model.coef_)),
        'intercept': final_model.intercept_
    }

    print(f"TimeSeries CV ({n_splits} разбиений) -> R²: {r2_mean:.4f} | MAE: {mae_mean:.4f}")
    print(f"Коэффициенты: {metrics['coefficients']}")
    print(f"Свободный член: {metrics['intercept']:.4f}")

    return final_model, metrics


def get_cov_matrix(returns_df):
    """
    returns_df : DataFrame с доходностями активов (столбцы – тикеры, строки – даты)
    Возвращает ковариационную матрицу (годовую или дневную – важно для оптимизации)
    """
    # Дневная ковариация
    cov_daily = returns_df.cov()
    # При желании можно перевести в годовую: cov_annual = cov_daily * 252
    return cov_daily


def get_apt_expected_return(file, ruonia_ind, fact, eps=0):
    stock_data = load_stock_data(file)
    stock_returns = stock_data["return"]
    rf_daily_pct = (1 + ruonia_ind) ** (1 / 252) - 1
    model, metrics = regress_stock_on_factors(stock_returns, fact, rf_daily_pct, n_splits=5)

    rf_mean_daily = rf_daily_pct.mean()
    rf_aligned = rf_daily_pct.reindex(fact.index).ffill()
    factor_premiums = [
        (fact["IMOEX"] - rf_aligned).mean(),
        fact["RUB_USD"].mean(),
        fact["BRENT"].mean()
    ]
    betas = list(metrics['coefficients'].values())

    exp_return = apt_expected_return(rf_mean_daily, betas, factor_premiums, eps)
    return exp_return


def optimize_tangency_portfolio(expected_returns, cov_matr, rf_rate):
    """
    expected_returns : список или массив ожидаемых доходностей активов (дневных)
    cov_matr     : ковариационная матрица (дневная)
    rf_rate          : дневная безрисковая ставка (например, средняя из ruonia)
    Возвращает оптимальные веса (массив) и максимальный Sharpe ratio.
    """
    n = len(expected_returns)
    # Начальные равные веса
    init_weights = np.ones(n) / n
    # Ограничения: сумма весов = 1
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
    # Границы: веса от 0 до 1 (без коротких позиций)
    bounds = tuple((0, 1) for _ in range(n))

    result = minimize(neg_sharpe, init_weights,
                      args=(expected_returns, cov_matr, rf_rate),
                      method='SLSQP', bounds=bounds, constraints=constraints)

    if not result.success:
        raise RuntimeError("Оптимизация не удалась: " + result.message)

    optimal_weights = result.x
    max_sharpe = -result.fun
    return optimal_weights, max_sharpe


def optimal_complete_portfolio(expected_returns, cov_matr, rf_rate, A=1.0):
    """
    Возвращает:
      - веса в каждом рисковом активе (в долях от всего капитала),
      - долю в безрисковом активе,
      - ожидаемую доходность и волатильность полного портфеля.
    """
    # 1. Находим касательный портфель (веса только рисковых активов, сумма=1)
    w_tang, sharpe = optimize_tangency_portfolio(expected_returns, cov_matr, rf_rate)

    # 2. Характеристики касательного портфеля
    ret_tang = np.sum(w_tang * expected_returns)
    vol_tang = np.sqrt(w_tang @ cov_matr @ w_tang)

    # 3. Доля в касательном портфеле (формула для одного рискового актива)
    y = (ret_tang - rf_rate) / (A * vol_tang ** 2)
    y = np.clip(y, 0, 1)  # ограничиваем от 0 до 1

    # 4. Итоговые веса: в рисковых активах = y * w_tang, в безрисковом = 1 - y
    final_weights_risky = y * w_tang
    final_weights_all = np.append(final_weights_risky, 1 - y)  # последний – безрисковый

    # 5. Характеристики полного портфеля
    port_ret = y * ret_tang + (1 - y) * rf_rate
    port_vol = y * vol_tang

    return {
        'tangency_weights': w_tang,  # веса в касательном портфеле (сумма=1)
        'y': y,  # доля в касательном портфеле
        'risky_weights': final_weights_risky,  # веса рисковых активов в полном портфеле
        'risk_free_weight': 1 - y,
        'expected_return': port_ret,
        'volatility': port_vol,
        'sharpe_ratio': sharpe
    }


if __name__ == "__main__":
    start = "2011-01-01"
    end = "2022-01-01"

    # Список акций
    stocks = {
        "AFLT.ME": "aeroflot.csv",  # Аэрофлот - крупнейшая авиакомпания РФ
        "SBER.ME": "sber.csv",  # Сбербанк - банк РФ
        "RUAL.ME": "rusal.csv",  # Русал - транспортная логистика
        "LKOH.ME": "lukoil.csv",  # Лукойл - нефтегазовых компания
        "NMTP.ME": "nmtp.csv"  # НМТП - морской торговый порт
    }

    ruonia_df = download_ruonia(start, end)
    factors = download__factors(start, end)

    all_returns = pd.DataFrame()  # колонки – тикеры, строки – даты
    exp_returns_dict = {}  # тикер -> ожидаемая доходность (APT)

    for ticker, filename in stocks.items():
        download_stock(ticker, filename, start, end)  # Скачиваем каждую акцию в отдельный файл

        # Загружаем доходности
        stock_data = load_stock_data(filename)
        all_returns[ticker] = stock_data["return"]

        exp_ret = get_apt_expected_return(filename, ruonia_df, factors)
        exp_returns_dict[ticker] = exp_ret

    # Собираем DataFrame доходностей (даты выравниваем по пересечению)
    returns_df = pd.DataFrame(all_returns).dropna()
    # Список ожидаемых доходностей в том же порядке, что и колонки returns_df
    exp_returns = np.array([exp_returns_dict[ticker] for ticker in returns_df.columns])

    # Безрисковая ставка (дневная средняя)
    rf_daily = (1 + ruonia_df) ** (1 / 252) - 1
    rf_mean = rf_daily.mean()

    # Ковариационная матрица
    cov_matrix = returns_df.cov()

    # Оптимизация портфеля
    portfolio = optimal_complete_portfolio(exp_returns, cov_matrix, rf_mean, A=5.0)

    print("\n=== РЕКОМЕНДАЦИЯ ПО ПОРТФЕЛЮ ===")
    for i, ticker in enumerate(returns_df.columns):
        print(f"{ticker}: {portfolio['risky_weights'][i] * 100:.2f}%")
    print(f"Безрисковый актив: {portfolio['risk_free_weight'] * 100:.2f}%")
    print(f"Ожидаемая доходность (дневная): {portfolio['expected_return']:.6f}")
    print(f"Волатильность (дневная): {portfolio['volatility']:.6f}")
    print(f"Коэффициент Шарпа (дневной): {portfolio['sharpe_ratio']:.4f}")

    weights_df = pd.DataFrame({
        'Компания': list(returns_df.columns) + ['Risk_free'],
        'Доля в портфеле': list(portfolio['risky_weights']) + [portfolio['risk_free_weight']]
    })
    weights_df.to_csv('portfolio.csv', index=False, encoding='utf-8')
    print("Рекомендации по портфелю сохранены в 'portfolio.csv'")
