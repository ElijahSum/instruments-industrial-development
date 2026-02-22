#!/bin/bash

# Обращаю внимание, что писал этот скрипт на MacOS, где из коробки доступен только древний bash 3.2, 
# поэтому у меня нет доступа к нормальному функционалу типа ассоциативных массивов :) 
# Поэтому в этом скрипте очень много awk...

# Проверяем наличие и корректность аргументов
if [ "$#" -ne 1 ]; then
    echo "Ошибка: Неверное количество аргументов."
    echo "Использование: $0 <путь_к_файлу>"
    exit 1
fi

FILE="$1"

# Проверяем наличие и корректности файла
if [ ! -f "$FILE" ]; then
    echo "Ошибка: Файл '$FILE' не найден."
    exit 1
elif [ ! -r "$FILE" ]; then
    echo "Ошибка: Нет прав на чтение файла '$FILE'."
    exit 1
fi

TMP_FILE=$(mktemp)
counter=0
buffer=""

for word in $(cat "$FILE"); do
    if [[ "$word" == "" ]]; then
        continue
    fi
    
    buffer="$buffer $word"
    counter=$((counter + 1))
    
    if [ "$counter" -eq 5 ]; then
        echo "$buffer" >> "$TMP_FILE"
        buffer=""
        counter=0
    fi
done

total_sales=$(awk '{sum += $4 * $5} END {print sum}' "$TMP_FILE")

# Подсчет дня с наибольшей выручкой
best_day_data=$(awk '{
    revenue = $4 * $5
    day = $1 " " $2
    d_rev[day] += revenue
} END {
    max_rev = 0
    best_day = ""
    for (d in d_rev) {
        if (d_rev[d] > max_rev) {
            max_rev = d_rev[d]
            best_day = d
        }
    }
    print best_day ";" max_rev
}' "$TMP_FILE")

# Надеюсь, awk использован корректно, 
# так как он уже выполняет все необходимые операции для подсчета дня с наибольшей выручкой и популярного товара :)


best_day=$(echo "$best_day_data" | cut -d';' -f1)
best_day_rev=$(echo "$best_day_data" | cut -d';' -f2)


best_prod_data=$(awk '{
    revenue = $4 * $5
    qty = $5
    prod = $3
    p_qty[prod] += qty
    p_rev[prod] += revenue
} END {
    max_qty = 0
    best_prod = ""
    for (p in p_qty) {
        if (p_qty[p] > max_qty) {
            max_qty = p_qty[p]
            best_prod = p
        }
    }
    print best_prod ";" max_qty ";" p_rev[best_prod]
}' "$TMP_FILE")

top_prod=$(echo "$best_prod_data" | cut -d';' -f1)
top_qty=$(echo "$best_prod_data" | cut -d';' -f2)
top_rev=$(echo "$best_prod_data" | cut -d';' -f3)

rm -f "$TMP_FILE"

echo "Общая сумма продаж: $total_sales"
echo "День с наибольшей выручкой: $best_day (сумма продаж: $best_day_rev)"
echo "Популярный товар: $top_prod (количество проданных единиц: $top_qty, сумма продаж: $top_rev)"
