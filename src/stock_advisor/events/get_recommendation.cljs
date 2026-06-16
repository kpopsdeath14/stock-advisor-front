(ns stock-advisor.events.get-recommendation
  (:require
   [ajax.core :as ajax]
   [stock-advisor.db :refer [app-state]]))

(def ^:private a-values {1 9, 2 3, 3 1})

(defn- handle-response [[ok? response]]
  (swap! app-state assoc :loading? false)
  (if ok?
    (swap! app-state assoc :portfolio response)
    (swap! app-state assoc :portfolio
           {:error (or (get-in response [:response :detail])
                       "Не удалось получить рекомендацию. Проверьте, запущен ли бэкенд.")})))

(defn get-recommendation []
  (let [A (get a-values (:risk-profile @app-state) 3)]
    (swap! app-state assoc :loading? true :portfolio nil)
    (ajax/ajax-request
     {:uri             "/portfolio-recommendation"
      :method          :post
      :params          {:A A}
      :handler         handle-response
      :format          (ajax/json-request-format)
      :response-format (ajax/json-response-format {:keywords? true})})))
