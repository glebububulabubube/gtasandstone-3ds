# gtasandstone
Свой минимальный движок для старой 3DS (Old 3DS) под ctrulib + citro3d.
Персонаж ходит / прыгает / бегает по простой тестовой карте.

## Сборка
Требуется devkitPro (devkitARM + libctru + citro3d).
```sh
make          # выдает gtasandstone.3dsx (hbmenu)
make          # + gtasandstone.cia (установка в меню)
```
GitHub Actions собирает и `.3dsx`, и `.cia` в артефактах.

## Управление
- Circle / D-pad — ходить
- B — прыгать
- R (зажать) — бег
- L — сброс камеры
- Start — выход

## Структура
- `source/` — код движка
- `include/` — заголовки