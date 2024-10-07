import requests
from .db import save_repo_to_db, save_starred_repo_to_db, save_followed_user_to_db, get_repo_count

async def get_github_repos(token, db_path):
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # 获取用户的仓库
    page = 1
    while True:
        url = f'https://api.github.com/user/repos?page={page}&per_page=100'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            repos = response.json()
            if not repos:
                break
            for repo in repos:
                if repo['fork']:
                    parent_url = f"https://api.github.com/repos/{repo['full_name']}"
                    parent_response = requests.get(parent_url, headers=headers)
                    if parent_response.status_code == 200:
                        parent_data = parent_response.json()
                        repo['parent'] = parent_data['parent']
                await save_repo_to_db(repo, db_path)
            page += 1
        else:
            print(f"获取仓库时出错: {response.status_code}")
            print(response.text)
            break

    # 获取用户标星的仓库
    page = 1
    while True:
        url = f'https://api.github.com/user/starred?page={page}&per_page=100'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            starred_repos = response.json()
            if not starred_repos:
                break
            for repo in starred_repos:
                await save_starred_repo_to_db(repo, db_path)
            page += 1
        else:
            print(f"获取标星仓库时出错: {response.status_code}")
            print(response.text)
            break

    # 获取用户关注的作者
    page = 1
    while True:
        url = f'https://api.github.com/user/following?page={page}&per_page=100'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            followed_users = response.json()
            if not followed_users:
                break
            for user in followed_users:
                await save_followed_user_to_db(user, db_path)
            page += 1
        else:
            print(f"获取关注的作者时出错: {response.status_code}")
            print(response.text)
            break