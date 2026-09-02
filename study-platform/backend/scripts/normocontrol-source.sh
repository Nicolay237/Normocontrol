#!/usr/bin/env sh
#
# Готовит исходники сервиса нормоконтроля рядом с репозиторием платформы.
#
# Берётся архив по HTTPS, а не git clone. Причина не в лени: с боевого хоста
# git-эндпоинт github.com закрыт наглухо — шесть попыток `git ls-remote` из
# шести отвечают «could not read Username», хотя обычный HTTPS к тому же
# github.com отдаёт 200. Тем же спотыкается и BuildKit, когда контекстом сборки
# указан git-адрес.
#
# Версия закреплена здесь и только здесь. Обновление сервиса — осознанная
# смена одной строки, а не то, что случилось само при очередной сборке.
#
# Имена переменных латиницей: скрипт исполняется /bin/sh, а dash кириллицу в
# именах не принимает и падает на «not found».
set -eu

COMMIT=ce868862943c28a0b68d0362cae87620f3cdb671
ARCHIVE="https://codeload.github.com/Nicolay237/Normocontrol/tar.gz/${COMMIT}"
# Соседним каталогом, а не внутри репозитория платформы: чужой код не должен
# попадать в наше рабочее дерево даже случайно.
DIR=$(cd "$(dirname "$0")/.." && pwd)/../normocontrol-src
STAMP="$DIR/.commit"

if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$COMMIT" ]; then
  echo "нормоконтроль: исходники уже на $COMMIT"
  exit 0
fi

TMP=$(mktemp -d)
# Каталог убирается при любом исходе, включая ошибку скачивания.
trap 'rm -rf "$TMP"' EXIT INT TERM

echo "нормоконтроль: скачиваю исходники на коммите $COMMIT"
curl -fsSL "$ARCHIVE" -o "$TMP/src.tgz"
mkdir -p "$TMP/src"
# Верхний каталог архива называется по коммиту — снимаем его.
tar xzf "$TMP/src.tgz" -C "$TMP/src" --strip-components=1

# Проверяем, что приехало то, из чего собирается образ: пустой или обрезанный
# архив иначе дошёл бы до docker и упал бы там непонятной ошибкой.
for f in Dockerfile requirements.txt app.py normocontrol.py; do
  [ -s "$TMP/src/$f" ] || { echo "нормоконтроль: в архиве нет $f" >&2; exit 1; }
done

# И что это версия с JSON-контрактом. Ранние версии на том же адресе отдают из
# /api/check готовый HTML-фрагмент — платформа такой ответ примет за
# несовместимый и будет отклонять каждую проверку. Ошибиться здесь дешевле,
# чем разбираться потом по коду incompatible_report.
if ! grep -q "serialize_report" "$TMP/src/app.py"; then
  echo "нормоконтроль: в этой версии /api/check отдаёт HTML, а не JSON." >&2
  echo "  Нужна версия с serialize_report — см. docs/normocontrol.md." >&2
  exit 1
fi

rm -rf "$DIR"
mv "$TMP/src" "$DIR"
printf '%s' "$COMMIT" > "$STAMP"
echo "нормоконтроль: исходники готовы в $DIR"
