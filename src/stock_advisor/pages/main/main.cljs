(ns stock-advisor.pages.main.main
  (:require
   ["antd" :as antd]
   ["recharts" :refer [AreaChart ResponsiveContainer XAxis YAxis CartesianGrid Tooltip Area]]
   [clojure.string :as str]
   [reagent.core :as r]
   [stock-advisor.db :refer [app-state stock-tickers stock-names]]
   [stock-advisor.events.get-recommendation :refer [get-recommendation]]))

;; Палитра
(def ^:private c-text    "#F0F6FF")
(def ^:private c-sub     "#8B949E")
(def ^:private c-muted   "#6E7681")
(def ^:private c-border  "#21262D")
(def ^:private c-border2 "#30363D")
(def ^:private c-card    "#161B22")
(def ^:private c-tooltip "#1C2128")
(def ^:private c-green   "#10B981")
(def ^:private c-yellow  "#F59E0B")
(def ^:private c-red     "#EF4444")
(def ^:private c-blue    "#60A5FA")

(def ^:private risk-colors {1 c-blue 2 c-yellow 3 c-red})

(def ^:private stock-colors
  {"AFLT.ME" c-green
   "SBER.ME" c-blue
   "RUAL.ME" c-yellow
   "LKOH.ME" "#A78BFA"
   "NMTP.ME" "#F472B6"})

(def ^:private signal-ru    {"buy" "ПОКУПАТЬ" "hold" "ДЕРЖАТЬ" "sell" "ПРОДАВАТЬ"})
(def ^:private signal-color {"buy" c-green "hold" c-yellow "sell" c-red})

(def ^:private card {:background c-card :border (str "1px solid " c-border) :border-radius 14})

(defn- date-formatter [v]
  (let [months #js ["Jan" "Feb" "Mar" "Apr" "May" "Jun"
                    "Jul" "Aug" "Sep" "Oct" "Nov" "Dec"]
        d (js/Date. v)]
    (str (aget months (.getMonth d)) " '" (.slice (.toString (.getFullYear d)) 2))))

(defonce selected-stock (r/atom (first stock-tickers)))

(defn stock-tabs []
  [:div {:style {:display "flex" :gap 6 :flex-wrap "wrap" :margin-bottom 16}}
   (for [ticker stock-tickers]
     (let [active? (= ticker @selected-stock)
           color   (get stock-colors ticker c-green)]
       ^{:key ticker}
       [:button
        {:on-click #(reset! selected-stock ticker)
         :style {:background    (if active? "rgba(255,255,255,0.04)" "transparent")
                 :border        (str "1px solid " (if active? color c-border))
                 :border-radius 8
                 :padding       "6px 14px"
                 :cursor        "pointer"
                 :color         (if active? color c-sub)
                 :font-size     13
                 :font-weight   (if active? 600 400)
                 :transition    "all 0.15s"}}
        (get stock-names ticker ticker)]))])

(defn price-chart []
  (let [ticker @selected-stock
        data   (get-in @app-state [:stocks-data ticker])
        color  (get stock-colors ticker c-green)
        gid    (str "grad-" (str/replace ticker #"\." "-"))]
    [:div
     [stock-tabs]
     [:div {:style {:display "flex" :align-items "baseline" :gap 10 :margin-bottom 12 :padding-left 4}}
      [:span {:style {:color c-sub :font-size 11 :text-transform "uppercase" :letter-spacing "0.6px"}} ticker]
      [:span {:style {:color c-text :font-size 18 :font-weight 700}} (get stock-names ticker ticker)]]
     (if (empty? data)
       [:div {:style {:height 240 :display "flex" :align-items "center"
                      :justify-content "center" :color c-muted :font-size 13}}
        "Загрузка..."]
       [:> ResponsiveContainer {:width "100%" :height 240}
        [:> AreaChart {:data (clj->js data) :margin {:top 4 :right 8 :left -10 :bottom 0}}
         [:defs
          [:linearGradient {:id gid :x1 "0" :y1 "0" :x2 "0" :y2 "1"}
           [:stop {:offset "0%"   :stopColor color :stopOpacity "0.25"}]
           [:stop {:offset "100%" :stopColor color :stopOpacity "0"}]]]
         [:> CartesianGrid {:stroke "#1E2535" :strokeDasharray "4 4" :vertical false}]
         [:> XAxis {:dataKey       "date"
                    :tick          {:fill c-muted :fontSize 11}
                    :tickLine      false
                    :axisLine      {:stroke c-border}
                    :interval      90
                    :tickFormatter date-formatter}]
         [:> YAxis {:tick          {:fill c-muted :fontSize 11}
                    :tickLine      false
                    :axisLine      false
                    :width         60
                    :tickFormatter (fn [v] (str "₽" (.toLocaleString v)))}]
         [:> Tooltip {:contentStyle #js {:background c-tooltip :border (str "1px solid " c-border2)
                                         :borderRadius 8 :padding "8px 14px"}
                      :labelStyle   #js {:color c-sub :fontSize 12 :marginBottom 4}
                      :itemStyle    #js {:color color :fontSize 14 :fontWeight 600}
                      :formatter    (fn [v] (clj->js [(str "₽" (.toLocaleString v)) "Цена"]))}]
         [:> Area {:type        "monotone"
                   :dataKey     "price"
                   :stroke      color
                   :strokeWidth 2
                   :fill        (str "url(#" gid ")")
                   :dot         false
                   :activeDot   #js {:r 5 :fill color :stroke "#0D1117" :strokeWidth 2}}]]])]))

(defn portfolio-row [{:keys [ticker name expected_return volatility optimal_share signal error]}]
  [:div {:style {:display "flex" :align-items "center" :padding "10px 0"
                 :border-bottom (str "1px solid " c-border)}}
   [:div {:style {:flex "0 0 90px" :color c-text :font-size 13 :font-weight 600}} ticker]
   [:div {:style {:flex "1" :color c-sub :font-size 13}} name]
   (if error
     [:div {:style {:flex "1" :color c-red :font-size 12}} error]
     [:<>
      [:div {:style {:flex "0 0 70px" :text-align "right" :color c-green :font-size 13 :font-weight 600}}
       (str expected_return "%")]
      [:div {:style {:flex "0 0 70px" :text-align "right" :color c-yellow :font-size 13}}
       (str volatility "%")]
      [:div {:style {:flex "0 0 80px" :text-align "right" :color c-blue :font-size 14 :font-weight 700}}
       (str optimal_share "%")]
      [:div {:style {:flex "0 0 90px" :text-align "right"}}
       [:span {:style {:color (get signal-color signal c-sub) :font-size 11
                       :font-weight 700 :letter-spacing "1px"}}
        (get signal-ru signal signal)]]])])

(def ^:private col-label {:color c-muted :font-size 11 :text-transform "uppercase" :letter-spacing "0.5px"})

(defn portfolio-section []
  (let [portfolio (:portfolio @app-state)
        loading?  (:loading? @app-state)]
    (cond
      loading?
      [:div {:style {:display "flex" :justify-content "center" :padding "32px 0"}}
       [:> antd/Spin {:size "large"}]]

      (and portfolio (:error portfolio))
      [:div {:style {:background "rgba(239,68,68,0.08)" :border (str "1px solid " c-red)
                     :border-radius 12 :padding "14px 18px" :color c-red :font-size 14}}
       (:error portfolio)]

      (and portfolio (:portfolio portfolio))
      [:div {:class "slide-up" :style (assoc card :padding "20px 24px")}
       [:div {:style {:color c-sub :font-size 13 :line-height 1.6 :margin-bottom 18}}
        "На основе предсказаний инвестиционного ассистента рекомендуется распределить "
        "ваш портфель в акции с такими долями:"]
       [:div {:style {:display "flex" :padding "0 0 8px"
                      :border-bottom (str "1px solid " c-border2) :margin-bottom 4}}
        [:div {:style (assoc col-label :flex "0 0 90px")} "Тикер"]
        [:div {:style (assoc col-label :flex "1")} "Компания"]
        [:div {:style (assoc col-label :flex "0 0 70px" :text-align "right")} "Доход."]
        [:div {:style (assoc col-label :flex "0 0 70px" :text-align "right")} "Риск"]
        [:div {:style (assoc col-label :flex "0 0 80px" :text-align "right")} "Доля"]
        [:div {:style (assoc col-label :flex "0 0 90px" :text-align "right")} "Сигнал"]]
       (for [row (:portfolio portfolio)]
         ^{:key (:ticker row)} [portfolio-row row])]

      :else nil)))

(defn main-page []
  (let [risk-profile (r/cursor app-state [:risk-profile])]
    [:div {:style {:max-width 900 :margin "0 auto" :padding "28px 16px 48px"}}
     [:div {:class "fade-in" :style {:margin-bottom 24}}
      [:h1 {:style {:color c-text :font-size 26 :font-weight 700 :margin 0}}
       "Инвестиционный ассистент"]
      [:div {:style {:color c-muted :font-size 13 :margin-top 4}}
       "Аэрофлот · ЮТэйр · Русал · FESCO · НМТП"]]

     [:div {:class "fade-in" :style (assoc card :padding "20px 16px 12px" :margin-bottom 16)}
      [price-chart]]

     [:div {:class "fade-in" :style (assoc card :padding "22px 24px" :margin-bottom 16)}
      [:span {:style {:color c-sub :font-size 13 :text-transform "uppercase"
                      :letter-spacing "0.6px" :display "block" :margin-bottom 14}}
       "Риск-профиль"]
      [:div {:style {:display "flex" :gap 10}}
       (for [[v label] [[1 "Консервативный"] [2 "Умеренный"] [3 "Агрессивный"]]]
         (let [active? (= v @risk-profile)
               color   (get risk-colors v)]
           ^{:key v}
           [:button
            {:on-click #(reset! risk-profile v)
             :style {:flex 1 :padding "12px 0"
                     :border-radius 10 :cursor "pointer"
                     :font-size 14 :font-weight (if active? 700 400)
                     :transition "all 0.15s"
                     :background (if active? "rgba(255,255,255,0.05)" "transparent")
                     :border     (str (if active? "1.5px" "1.5px") " solid " (if active? color c-border))
                     :color      (if active? color c-muted)}}
            label]))]]

     [:> antd/Button {:type    "primary"
                      :size    "large"
                      :loading (:loading? @app-state)
                      :onClick get-recommendation
                      :style   {:width "100%" :height 52 :font-size 16 :font-weight 600
                                :border-radius 12 :border "none" :margin-bottom 16
                                :box-shadow "0 4px 24px rgba(16,185,129,0.3)"
                                :letter-spacing "0.3px"}}
      "Получить рекомендацию"]

     [portfolio-section]]))
