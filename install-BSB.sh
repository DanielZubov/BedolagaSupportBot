#!/bin/bash

# Цвета для красивого вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# НАСТРОЙКИ РЕПОЗИТОРИЯ (Укажи свой URL)
REPO_URL="https://github.com/DanielZubov/BedolagaSupportBot.git"
REPO_DIR="BedolagaSupportBot"
CONTAINER_NAME="bedolaga_support_bot"

draw_header() {
    clear
    echo -e "${BLUE}==================================================${NC}"
    echo -e "${BLUE}          Bedolaga Support Bot Manager            ${NC}"
    echo -e "${BLUE}==================================================${NC}"
}

check_dependencies() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker не установлен! Установите его перед запуском.${NC}"
        exit 1
    fi
    if ! command -v git &> /dev/null; then
        echo -e "${RED}❌ Git не установлен! Установите его перед запуском.${NC}"
        exit 1
    fi
}

# Функция перехода в корень репозитория
ensure_repo_dir() {
    # Если мы уже внутри папки репозитория (есть .git)
    if [ -d ".git" ]; then
        return
    fi

    # Если мы снаружи, но папка уже создана — заходим в неё
    if [ -d "$REPO_DIR" ]; then
        cd "$REPO_DIR" || exit 1
        return
    fi

    # Если папки нет, значит это первая установка — клонируем
    echo -e "${YELLOW}📥 Клонирование репозитория...${NC}"
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR" || exit 1
}

# 1. Установка бота
install_bot() {
    draw_header
    echo -e "${YELLOW}🚀 Настройка окружения и установка...${NC}\n"

    # Проверяем и клонируем репозиторий, если нужно
    ensure_repo_dir

    if [ -f .env ]; then
        echo -e "${YELLOW}⚠️ Файл .env уже существует.${NC}"
        read -p "Перезаписать его? (y/N): " res
        if [[ ! "$res" =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}🔄 Пропускаем генерацию .env, запускаем контейнеры...${NC}"
            docker compose up -d --build
            read -p "Нажмите Enter для возврата в меню..."
            return
        fi
    fi

    # Запрос переменных у пользователя
    read -p "Введите SUPPORT_BOT_TOKEN: " bot_token
    read -p "Введите ADMIN_IDS (через запятую): " admin_ids
    read -p "Введите POSTGRES_USER [db_user]: " pg_user
    pg_user=${pg_user:-db_user}
    read -s -p "Введите POSTGRES_PASSWORD [секретный пароль]: " pg_password
    echo ""
    pg_password=${pg_password:-secret_pass}
    read -p "Введите POSTGRES_DB [support_db]: " pg_db
    pg_db=${pg_db:-support_db}

    # Запись в .env
    cat <<EOF > .env
SUPPORT_BOT_TOKEN=${bot_token}
ADMIN_IDS=${admin_ids}
POSTGRES_USER=${pg_user}
POSTGRES_PASSWORD=${pg_password}
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=${pg_db}
REDIS_URL=redis://redis:6379/1
EOF

    echo -e "\n${GREEN}✅ Файл .env успешно создан!${NC}"
    echo -e "${YELLOW}🐳 Запускаем Docker контейнеры...${NC}"
    
    docker compose up -d --build
    
    echo -e "${GREEN}🏁 Бот успешно установлен и запущен!${NC}"
    read -p "Нажмите Enter для возврата в меню..."
}

# 2. Перезапуск бота
restart_bot() {
    draw_header
    ensure_repo_dir
    echo -e "${YELLOW}🔄 Перезапуск всех сервисов...${NC}"
    docker compose restart
    echo -e "${GREEN}✅ Сервисы перезапущены.${NC}"
    read -p "Нажмите Enter для возврата в меню..."
}

# 3. Обновление бота через Git Pull
update_bot() {
    draw_header
    ensure_repo_dir
    echo -e "${YELLOW}🔄 Проверка обновлений в Git...${NC}"
    
    # Стягиваем изменения
    git pull
    
    echo -e "${YELLOW}📥 Пересборка контейнеров после обновления...${NC}"
    docker compose up -d --build
    echo -e "${GREEN}✅ Бот успешно обновлен до последней версии Git!${NC}"
    read -p "Нажмите Enter для возврата в меню..."
}

# 4. Просмотр логов
show_logs() {
    draw_header
    ensure_repo_dir
    echo -e "${BLUE}📋 Вывод логов бота (Для выхода нажмите Ctrl+C)...${NC}\n"
    docker logs -f $CONTAINER_NAME
}

# 5. Полное удаление
uninstall_bot() {
    draw_header
    if [ -d ".git" ] || [ -d "$REPO_DIR" ]; then
        ensure_repo_dir
        echo -e "${RED}⚠️⚠️⚠️ ВНИМАНИЕ! Полное удаление уничтожит контейнеры, базу данных и папку с ботом!${NC}"
        read -p "Вы уверены, что хотите удалить ВСЁ? (укажите 'yes' для подтверждения): " confirm
        
        if [ "$confirm" = "yes" ]; then
            echo -e "${YELLOW}🗑️ Останавливаем контейнеры и удаляем Volumes...${NC}"
            docker compose down -v
            
            cd ..
            echo -e "${YELLOW}🗑️ Удаляем директорию проекта ${REPO_DIR}...${NC}"
            rm -rf "$REPO_DIR"
            echo -e "${GREEN}✅ Бот и все его данные полностью удалены!${NC}"
        else
            echo -e "${GREEN}❌ Удаление отменено.${NC}"
        fi
    else
        echo -e "${YELLOW}ℹ️ Репозиторий еще не развернут, удалять нечего.${NC}"
    fi
    read -p "Нажмите Enter для возврата в меню..."
}

# Главный цикл
check_dependencies

while true; do
    draw_header
    echo -e "1. ${GREEN}🚀 Скачать репозиторий, настроить .env и запустить бота${NC}"
    echo -e "2. ${YELLOW}🔄 Перезапустить сервисы${NC}"
    echo -e "3. ${BLUE}📥 Обновить бота (git pull + пересборка)${NC}"
    echo -e "4. ${NC}📋 Посмотреть логи бота${NC}"
    echo -e "5. ${RED}🗑️ Полностью удалить бота, базу данных и репозиторий${NC}"
    echo -e "0. Выход"
    echo -e "${BLUE}==================================================${NC}"
    read -p "Выберите действие [0-5]: " choice

    case $choice in
        1) install_bot ;;
        2) restart_bot ;;
        3) update_bot ;;
        4) show_logs ;;
        5) uninstall_bot ;;
        0) clear; echo "Пока!"; exit 0 ;;
        *) echo -e "${RED}Неверный пункт меню!${NC}"; sleep 1 ;;
    esac
done
