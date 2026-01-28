# Setup script
import os


def create_project_structure():
    dirs = [
        'config',
        'data',
        'logs',
        'src/collectors',
        'src/storage',
        'src/alerts',
        'src/notifiers',
        'tests'
    ]

    for dir in dirs:
        os.makedirs(dir, exist_ok=True)
        if dir.startswith('src/'):
            open(f'{dir}/__init__.py', 'a').close()

    # Create placeholder files
    open('data/.gitkeep', 'a').close()
    open('logs/.gitkeep', 'a').close()

    print("Project structure created successfully!")


if __name__ == '__main__':
    create_project_structure()
