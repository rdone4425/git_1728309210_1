import os
import aiohttp
import asyncio
import aiosqlite
import base64
import json
import time

async def upload_repo(token, repo_name, description, db_path, paths):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    original_repo_name = repo_name
    attempt = 0
    repo_data = None
    
    async with aiohttp.ClientSession() as session:
        while True:
            data = {
                "name": repo_name,
                "description": description,
                "private": False
            }
            
            async with session.post("https://api.github.com/user/repos", headers=headers, json=data) as response:
                if response.status == 201:
                    repo_data = await response.json()
                    break
                elif response.status == 422:  # Unprocessable Entity, likely due to name conflict
                    error_data = await response.json()
                    if any(error.get('field') == 'name' for error in error_data.get('errors', [])):
                        attempt += 1
                        repo_name = f"{original_repo_name}_{int(time.time())}_{attempt}"
                        continue
                else:
                    error_data = await response.json()
                    error_message = error_data.get('message', '未知错误')
                    if 'errors' in error_data:
                        error_message += ": " + json.dumps(error_data['errors'])
                    return False, f"创建仓库失败: {error_message}"
        
        if repo_data is None:
            return False, "创建仓库失败: 未知错误"
        
        # 上传文件和文件夹
        for path in paths:
            if os.path.isfile(path):
                await upload_file(session, headers, repo_data['full_name'], path)
            elif os.path.isdir(path):
                await upload_folder(session, headers, repo_data['full_name'], path)
    
    # 将仓库信息保存到数据库
    await insert_repo(db_path, repo_data)
    
    return True, f"仓库 '{repo_name}' 创建成功"

async def upload_file(session, headers, repo_full_name, file_path, relative_path=None):
    with open(file_path, 'rb') as file:
        content = file.read()
    
    encoded_content = base64.b64encode(content).decode()
    file_name = relative_path if relative_path else os.path.basename(file_path)
    
    data = {
        "message": f"Add {file_name}",
        "content": encoded_content
    }
    
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_name}"
    async with session.put(url, headers=headers, json=data) as response:
        if response.status != 201:
            print(f"上传文件 {file_name} 失败")

async def upload_folder(session, headers, repo_full_name, folder_path):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, folder_path)
            await upload_file(session, headers, repo_full_name, file_path, relative_path)

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
