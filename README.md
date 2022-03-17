## Парсер профилей инстаграм.

![alt text](https://raw.githubusercontent.com/aorews/instagram_parser/main/example/Screenshot%20from%202022-02-22%2019-59-57.png)
![alt text](https://raw.githubusercontent.com/aorews/instagram_parser/main/example/Screenshot%20from%202022-02-22%2020-00-20.png)

Строит граф связей между подписчиками и подписками доступного профиля, кластеризует полученный граф с помощью алгоритма Гирван — Ньюмена. 

Сначала нужно запустить скрипт для сбора информации

python3 parse.py --credentials YOUR_USERNAME,YOUR_PASSWORD --target TARGET_USERNAME 

Для перезапуска скрипта и загрузки сохраненной информации использовать параметр
--load_state PATH

После загрузки получить визуальное представление графа с помощью

python3 display.py --path PATH --clusters NUM_CLUSTERS

Готовый пример есть в файле example.html
