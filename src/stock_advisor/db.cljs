(ns stock-advisor.db
  (:require [reagent.core :as r]))

(def stock-tickers ["AFLT.ME" "SBER.ME" "RUAL.ME" "LKOH.ME" "NMTP.ME"])

(def stock-names
  {"AFLT.ME" "Аэрофлот"
   "SBER.ME" "Сбербанк"
   "RUAL.ME" "Русал"
   "LKOH.ME" "Лукойл"
   "NMTP.ME" "НМТП"})

(defonce app-state
  (r/atom {:risk-profile  2
           :stocks-data   {}
           :portfolio     nil
           :loading?      false}))
