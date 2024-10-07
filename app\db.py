import os
import aiosqlite
from datetime import datetime

async def init_database(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
        CREATE TABLE IF NOT EXISTS repos (
            full_name TEXT PRIMARY KEY,
            github_id INTEGER UNIQUE,
            name TEXT,
            description TEXT,
            html_url TEXT,
            stargazers_count INTEGER,
            owner_login TEXT,
            owner_html_url TEXT,
            owner_avatar_url TEXT,
            is_fork BOOLEAN,
            updated_at TEXT,
            parent_full_name TEXT,
            parent_html_url TEXT,
            parent_owner_login TEXT,
            parent_owner_html_url TEXT,
            parent_owner_avatar_url TEXT,
            parent_updated_at TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS starred_repos (
            full_name TEXT PRIMARY KEY,
            github_id INTEGER UNIQUE,
            name TEXT,
            description TEXT,
            html_url TEXT,
            stargazers_count INTEGER,
            owner_login TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS followed_users (
            login TEXT PRIMARY KEY,
            github_id INTEGER UNIQUE,
            html_url TEXT,
            avatar_url TEXT
        )
        ''')

        await db.commit()

async def save_repo_to_db(repo, db_path):
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT updated_at FROM repos WHERE full_name = ?", (repo['full_name'],))
        existing = await cursor.fetchone()

        if existing:
            existing_updated_at = datetime.strptime(existing[0], "%Y-%m-%dT%H:%M:%SZ")
            new_updated_at = datetime.strptime(repo['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
            if new_updated_at > existing_updated_at:
                await db.execute('''
                UPDATE repos SET
                    name = ?, description = ?, html_url = ?, stargazers_count = ?,
                    owner_login = ?, owner_html_url = ?, owner_avatar_url = ?, is_fork = ?,
                    updated_at = ?, parent_full_name = ?, parent_html_url = ?,
                    parent_owner_login = ?, parent_owner_html_url = ?,
                    parent_owner_avatar_url = ?, parent_updated_at = ?
                WHERE full_name = ?
                ''', (
                    repo['name'], repo['description'], repo['html_url'],
                    repo['stargazers_count'], repo['owner']['login'], repo['owner']['html_url'],
                    repo['owner']['avatar_url'], repo['fork'], repo['updated_at'],
                    repo.get('parent', {}).get('full_name'),
                    repo.get('parent', {}).get('html_url'),
                    repo.get('parent', {}).get('owner', {}).get('login'),
                    repo.get('parent', {}).get('owner', {}).get('html_url'),
                    repo.get('parent', {}).get('owner', {}).get('avatar_url'),
                    repo.get('parent', {}).get('updated_at'),
                    repo['full_name']
                ))
        else:
            await db.execute('''
            INSERT OR REPLACE INTO repos (
                full_name, github_id, name, description, html_url, stargazers_count,
                owner_login, owner_html_url, owner_avatar_url, is_fork, updated_at,
                parent_full_name, parent_html_url, parent_owner_login,
                parent_owner_html_url, parent_owner_avatar_url, parent_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo['full_name'], repo['id'], repo['name'], repo['description'], repo['html_url'],
                repo['stargazers_count'], repo['owner']['login'], repo['owner']['html_url'],
                repo['owner']['avatar_url'], repo['fork'], repo['updated_at'],
                repo.get('parent', {}).get('full_name'),
                repo.get('parent', {}).get('html_url'),
                repo.get('parent', {}).get('owner', {}).get('login'),
                repo.get('parent', {}).get('owner', {}).get('html_url'),
                repo.get('parent', {}).get('owner', {}).get('avatar_url'),
                repo.get('parent', {}).get('updated_at')
            ))

        await db.commit()

async def save_starred_repo_to_db(repo, db_path):
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT stargazers_count FROM starred_repos WHERE full_name = ?", (repo['full_name'],))
        existing = await cursor.fetchone()

        if existing:
            if repo['stargazers_count'] != existing[0]:
                await db.execute('''
                UPDATE starred_repos SET
                    name = ?, description = ?, html_url = ?, stargazers_count = ?, owner_login = ?
                WHERE full_name = ?
                ''', (
                    repo['name'], repo['description'], repo['html_url'],
                    repo['stargazers_count'], repo['owner']['login'], repo['full_name']
                ))
        else:
            await db.execute('''
            INSERT INTO starred_repos (
                full_name, github_id, name, description, html_url, stargazers_count, owner_login
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo['full_name'], repo['id'], repo['name'], repo['description'], repo['html_url'],
                repo['stargazers_count'], repo['owner']['login']
            ))

        await db.commit()

async def save_followed_user_to_db(user, db_path):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
        INSERT OR REPLACE INTO followed_users (
            login, github_id, html_url, avatar_url
        ) VALUES (?, ?, ?, ?)
        ''', (
            user['login'], user['id'], user['html_url'], user['avatar_url']
        ))

        await db.commit()

async def get_repo_count(db_path):
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM repos")
        count = await cursor.fetchone()
        return count[0]

async def get_all_repos(db_path):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
        SELECT name, full_name, description, html_url, stargazers_count,
               owner_login, is_fork, parent_full_name, parent_html_url
        FROM repos
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_starred_repos(db_path):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM starred_repos")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_followed_users(db_path):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM followed_users ORDER BY login")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def insert_repo(db_path, repo_data):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            INSERT OR REPLACE INTO repos (
                id, name, full_name, description, html_url, stargazers_count, 
                language, forks_count, open_issues_count, owner_id, owner_login, 
                owner_avatar_url, owner_html_url, is_fork, parent_full_name, 
                parent_html_url, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            repo_data['id'], repo_data['name'], repo_data['full_name'],
            repo_data.get('description'), repo_data['html_url'],
            repo_data['stargazers_count'], repo_data.get('language'),
            repo_data['forks_count'], repo_data['open_issues_count'],
            repo_data['owner']['id'], repo_data['owner']['login'],
            repo_data['owner']['avatar_url'], repo_data['owner']['html_url'],
            repo_data['fork'], repo_data.get('parent', {}).get('full_name'),
            repo_data.get('parent', {}).get('html_url'), repo_data['updated_at']
        ))
        await db.commit()