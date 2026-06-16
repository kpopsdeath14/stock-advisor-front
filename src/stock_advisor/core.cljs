(ns stock-advisor.core
  (:require
   ["antd" :as antd]
   [reagent.core :as r]
   [reagent.dom :as d]
   [stock-advisor.db :refer [app-state stock-tickers]]
   [stock-advisor.pages.main.main :refer [main-page]]))

(defn- load-stock-prices [ticker]
  (-> (js/fetch (str "/api/v1/stocks/" ticker "/price-history"))
      (.then (fn [res] (.json res)))
      (.then (fn [data]
               (let [parsed    (js->clj data :keywordize-keys true)
                     price-data (mapv (fn [b] {:date  (:date b)
                                               :price (:close b)})
                                      (:bars parsed))]
                 (swap! app-state assoc-in [:stocks-data ticker] price-data))))
      (.catch (fn [e]
                (js/console.warn "Не удалось загрузить" ticker e)))))

(defn- load-all-stocks []
  (doseq [ticker stock-tickers]
    (load-stock-prices ticker)))

(defn root-component []
  (let [ConfigProvider antd/ConfigProvider
        theme          (.-theme antd)
        dark-algo      (.-darkAlgorithm theme)]
    [:> ConfigProvider
     {:theme (clj->js {:algorithm  dark-algo
                        :token      {:colorPrimary       "#10B981"
                                     :colorBgBase        "#0D1117"
                                     :colorBgContainer   "#161B22"
                                     :colorBgElevated    "#1C2128"
                                     :colorBorder        "#30363D"
                                     :colorText          "#F0F6FF"
                                     :colorTextSecondary "#8B949E"
                                     :borderRadius       10
                                     :fontFamily         "'Inter', -apple-system, sans-serif"}
                        :components {:Slider {:trackBg      "#10B981"
                                              :trackHoverBg "#059669"
                                              :handleColor  "#10B981"
                                              :railBg       "#21262D"
                                              :railHoverBg  "#30363D"}
                                     :Button {:primaryColor "#0D1117"}}})
      :wave {:disabled true}}
     [main-page]]))

(defn mount-root []
  (d/render [root-component] (.getElementById js/document "app")))

(defn ^:export init! []
  (load-all-stocks)
  (mount-root))
