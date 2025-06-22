import os
import sys
import zipfile
import shutil
from datetime import datetime
import dropbox
from dropbox import files
from dropbox.exceptions import AuthError, ApiError
from tqdm import tqdm

valheim_saves_path = os.path.expanduser('~\\AppData\\LocalLow\\IronGate\\Valheim\\worlds_local')
dropbox_token = ''
dropbox_folder = '/Valheim_Worlds'

class valheim_backup:
    def __init__(self):
        self.dbx = None
        self._init_dropbox()

    def _init_dropbox(self):

        try:
            self.dbx = dropbox.Dropbox(dropbox_token)
            self.dbx.users_get_current_account()
            print('\n✅ Успешное подключение к Dropbox')

            try:
                self.dbx.files_get_metadata(dropbox_folder)
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    self.dbx.files_create_folder_v2(dropbox_folder)
                    print(f"📁 Создана папка {dropbox_folder} в Dropbox")

        except AuthError:
            print('\n❌ Ошибка авторизации в Dropbox. Проверьте токен доступа.')
            sys.exit(1)

    def list_worlds(self):
        if not os.path.exists(valheim_saves_path):
            print('\n❌ Папка с мирами Valheim не найдена!')
            print(f"Проверьте путь: {valheim_saves_path}")
            return []

        files = os.listdir(valheim_saves_path)
        worlds = set()

        for file in files:
            if file.endswith('.fwl') and not file.endswith('fwl.old'):
                worlds.add(file[:-4])

        return sorted(worlds)

    def get_worlds_files(self, world_name):
        return [
            f'{world_name}.fwl',
            f'{world_name}.fwl.old',
            f'{world_name}.db',
            f'{world_name}.db.old'
        ]

    def list_backups(self):
        try:
            backups = {}
            result = self.dbx.files_list_folder(dropbox_folder)

            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    name = entry.name
                    if name.startswith('valheim_') and name.endswith('.zip'):
                        parts = name[8:-4].split('_')
                        world_name = '_'.join(parts[:-5])
                        date_str = '_'.join(parts[-5:])

                        if world_name not in backups:
                            backups[world_name] = []
                        backups[world_name].append({
                            'name': name,
                            'path': entry.path_display,
                            'date': date_str,
                            'size': entry.size
                        })
            return backups
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                print("\n❌ Папка с бэкапами не найдена в Dropbox")
                return {}
            print(f"\n❌ Ошибка Dropbox: {e}")
            return {}

    def create_backup(self, world_name):
        print(f"\n=== Создание бэкапа мира '{world_name}' ===")

        world_files = self.get_worlds_files(world_name)
        existing_files = []

        for file in world_files:
            if os.path.exists(os.path.join(valheim_saves_path, file )):
                existing_files.append(file)
            else:
                print(f"⚠️ Файл {file} не найден, пропускаем")

        if not existing_files:
            print("❌ Нет файлов для создания бэкапа")
            return False

        backup_name = f"valheim_{world_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip"
        backup_path = os.path.join(os.getcwd(), backup_name)

        print("\n📦 Архивируем файлы...")
        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in existing_files:
                    file_path = os.path.join(valheim_saves_path, file)
                    zipf.write(file_path, file)
                    print(f"- Добавлен: {file}")
        except Exception as e:
            print(f"❌ Ошибка при создании архива: {str(e)}")
            return False

        print('\n☁️ Загружаем в Dropbox...')
        try:
            with open(backup_path, 'rb') as f:
                file_size = os.path.getsize(backup_path)
                with tqdm(total=file_size, unit='B', unit_scale=True, desc=backup_name) as pbar:
                    self.dbx.files_upload(
                        f.read(),
                        f'{dropbox_folder}/{backup_name}'
                    )
            os.remove(backup_path)
            print(f"\n✅ Бэкап успешно загружен: {backup_name}")
            return True
        except Exception as e:
            print(f"❌ Ошибка загрузки: {str(e)}")
            if os.path.exists(backup_path):
                os.remove(backup_path)
            return False

    def restore_backup(self, backup_path, backup_name):
        print(f"\n=== Восстановление мира из {backup_name} ===")

        temp_zip = 'temp_valheim_backup.zip'

        print("\n⬇️ Скачиваем бэкап...")
        try:
            self.dbx.files_download_to_file(temp_zip, backup_path)
        except Exception as e:
            print(f"❌ Ошибка скачивания: {str(e)}")
            return False

        print("\n📦 Распаковываем файлы...")
        try:
            with zipfile.ZipFile(temp_zip, 'r') as zipf:
                for file in zipf.namelist():
                    original_path = os.path.join(valheim_saves_path, file)
                    if os.path.exists(original_path):
                        backup_path = original_path + '.bak'
                        shutil.move(original_path, backup_path)
                        print(f"- Создана резервная копия: {file}.bak")

                zipf.extractall(valheim_saves_path)
                for file in zipf.namelist():
                    print(f'- Восстановлен: {file}')

            os.remove(temp_zip)
            print("\n✅ Мир успешно восстановлен!")
            return True
        except Exception as e:
            print(f"❌ Ошибка распаковки: {str(e)}")
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            return False

    def menu_create_backup(self):

        worlds = self.list_worlds()

        if not worlds:
            print("\n❌ Локальные миры не найдены!")
            print("1. Убедитесь, что игра Valheim установлена")
            print(f"2. Проверьте путь к сохранениям: {valheim_saves_path}")
            return

        print("\nДоступные миры:")
        for i, world in enumerate(worlds, 1):
            print(f"{i}. {world}")

        try:
            choice = int(input("\nВыберите мир для бэкапа: ")) - 1
            if 0 <= choice < len(worlds):
                self.create_backup(worlds[choice])
            else:
                print("\n❌ Неверный выбор")
        except ValueError:
            print("\n❌ Введите число")

    def menu_restore_backup(self):

        backups = self.list_backups()

        if not backups:
            print("\n❌ В Dropbox нет бэкапов")
            return

        print("\nДоступные бэкапы:")
        for i, (world_name, world_backups) in enumerate(backups.items(), 1):
            print(f"\nМир: {world_name}")
            for j, backup in enumerate(world_backups, 1):
                print(f"  {i}.{j} | {backup['date']} | {backup['size']} bytes")

        try:
            choice = input("\nВведите номер бэкапа (например 1.2): ")
            main_idx, sub_idx = map(int, choice.split('.'))
            world_name = list(backups.keys())[main_idx - 1]
            backup = backups[world_name][sub_idx - 1]

            confirm = input(f"\nВосстановить мир '{world_name}' из бэкапа {backup['date']}? (y/n): ")
            if confirm.lower() == 'y':
                self.restore_backup(backup['path'], backup['name'])
        except (ValueError, IndexError):
            print("\n❌ Неверный выбор")
        except Exception as e:
            print(f"\n❌ Ошибка: {str(e)}")


    def menu(self):

        while True:
            print("\n=== Valheim Dropbox Backup ===")
            print("1. Создать бэкап мира")
            print("2. Восстановить мир из бэкапа")
            print("3. Выход")

            choice = input("\nВыберите действие: ").strip()

            if choice == "1":
                self.menu_create_backup()
            elif choice == "2":
                self.menu_restore_backup()
            elif choice == "3":
                print("\nДо свидания!")
                sys.exit(0)
            else:
                print("\n❌ Неверный выбор, попробуйте снова")


if __name__ == '__main__':
    # Проверка токена
    if dropbox_token == "ВАШ_ACCESS_TOKEN":
        print("\n❌ Замените DROPBOX_TOKEN в коде на свой access token")
        sys.exit(1)

    try:
        backup_tool = valheim_backup()
        backup_tool.menu()
    except KeyboardInterrupt:
        print("\n\nПрограмма завершена")
        sys.exit(0)