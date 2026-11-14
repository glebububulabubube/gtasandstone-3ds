# gtasandstone
Свой минимальный 3D-движок для старой 3DS (Old 3DS) под ctrulib + citro3d.
Порт GTA San Andreas для 3DS: персонаж CJ и карта, загружаемая по секторам.

Иконка приложения — `icon.png` (обложка GTA San Andreas). Кладётся в корень,
`smdhtool` встраивает её в SMDH (.3dsx и .cia).

## Сборка
Требуется devkitPro (devkitARM + libctru + citro3d).
```sh
make          # выдает gtasandstone.3dsx (hbmenu)
make          # + gtasandstone.cia (установка в меню)
```
GitHub Actions собирает и `.3dsx`, и `.cia` в артефактах.

## Управление
- Circle pad — ходить
- B — прыгать
- R (зажать) — бег
- L — сброс камеры
- Start — выход

## Что внутри
- Персонаж CJ: настоящая модель (5 частей из GTA SA, скелет 38 костей,
  скининг, процедурные анимации walk/run/jump/idle, текстуры).
- Карта: район Гроув-стрит (GTA SA), разбит на сектора 200×200 —
  подгружаются только сектора вокруг игрока (стриминг).
- Форматы: `.gsmod` (модель), `.gsmap` (карта) — собираются Python-скриптами
  из исходных файлов GTA SA (`models/`, `data/maps/`).

## Структура
- `source/` — код движка
- `include/` — заголовки
- `assets/` — бинарные ассеты (cj.bin, grove.bin)
- `tools/` — Python-конвертеры (IPL/IDE/DFF/TXD → .gsmod/.gsmap)