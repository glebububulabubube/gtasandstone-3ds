#pragma once
// Меню gtasandstone: интро-видео (ETC1-кадры), титульный экран, кнопки SKIP/PLAY.
// Ассеты вшиты через bin2o: intro_bin/title_bin/skip_bin/play_bin (+ *_size).

#include <3ds.h>
#include <citro3d.h>

namespace stone {

enum class MenuMode {
    MENU_INTRO,   // показываем кадр видео + кнопку SKIP на нижнем экране
    MENU_TITLE    // показываем титул + кнопку PLAY на нижнем экране
};

// Загружает вшитые ассеты в текстуры (меню). Вызывать до цикла.
void MenuInit();

// Освобождает текстуры меню.
void MenuShutdown();

// Число кадров интро-видео (из intro.bin), или 0 если нет.
int MenuIntroFrames();

// Отрисовывает один кадр меню. Возвращает 1, если нажата кнопка (SKIP/PLAY),
// иначе 0. Вызывать из цикла.
//   mode: какой экран рисуем
//   frame: индекс кадра видео (для MENU_INTRO)
//   touchX/touchY: координаты касания нижнего экрана (px)
//   touchDown: true, если касание было в этом кадре (KEY_TOUCH)
int MenuFrame(MenuMode mode, int frame, int touchX, int touchY, bool touchDown);

} // namespace stone