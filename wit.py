import filecmp
import os
import random
import shutil
import sys
import time

import graphviz


def get_activated(activated_path):
    with open(activated_path, 'r') as activated_file:
        activated = activated_file.read()
    if activated == 'None':
        return None
    return activated


def update_activated(activated_path, activated):
    with open(activated_path, 'w') as activated_file:
        activated_file.write(str(activated))


def init():
    path = os.getcwd()
    wit_path = os.path.join(path, '.wit')
    folders = ('images', 'staging_area')
    for folder in folders:
        path_folder = os.path.join(wit_path, folder)
        os.makedirs(path_folder, exist_ok=True)
    activated_path = os.path.join(wit_path, 'activated.txt')
    update_activated(activated_path, 'master')


def get_wit_path(path):
    if os.path.isdir(path) and '.wit' in os.listdir(path):
        return os.path.join(path, '.wit')
    parent_path = os.path.dirname(path)
    if parent_path == path:
        raise OSError('No .wit directory')
    return get_wit_path(parent_path)


def copy(src_full_path, src_relative_path, dst_path):
    new_path = os.path.join(dst_path, src_relative_path)
    try:
        shutil.copytree(src_full_path, new_path, dirs_exist_ok=True)
    except NotADirectoryError:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.copyfile(src_full_path, new_path)


def add(add_path):
    absolute_path = os.path.abspath(add_path)
    wit_path = get_wit_path(absolute_path)
    staging_area_path = os.path.join(wit_path, 'staging_area')
    relative_path = os.path.relpath(absolute_path, os.path.dirname(wit_path))
    copy(src_full_path=absolute_path, src_relative_path=relative_path, dst_path=staging_area_path)


def get_references(path):
    try:
        with open(path, 'r') as references_file:
            head = references_file.readline().split('=')[1].strip()
            master = references_file.readline().split('=')[1].strip()
            branches = {
                branch.split('=')[0]: branch.split('=')[1].strip()
                for branch in references_file.readlines()
            }
        return head, master, branches
    except FileNotFoundError:
        return None, None, None


def update_references(path, commit_id, activated_branch=None):
    head, master, branches = get_references(path)
    if activated_branch:
        if activated_branch == 'master':
            master = commit_id
        else:
            branches[activated_branch] = commit_id
    with open(path, 'w') as references_file:
        references_file.write(
            f"HEAD={commit_id}\n"
            f"master={master}\n"
        )
        if branches:
            for branch_name, branch_commit in branches.items():
                references_file.write(f"{branch_name}={branch_commit}\n")


def create_metadata(head, branch_marge_parent, commit_id_metadata_path, massage):
    parent = head
    if branch_marge_parent:
        parent += f', {branch_marge_parent}'
    with open(commit_id_metadata_path, 'w') as metadata_file:
        c_time = os.path.getctime(commit_id_metadata_path)
        date = time.ctime(c_time)
        metadata_file.write(
            f"parent={parent}\n"
            f"date={date}\n"
            f"message={massage}\n"
        )


def commit(massage, branch_marge_parent=None):
    wit_path = get_wit_path(os.getcwd())
    references_path = os.path.join(wit_path, 'references.txt')
    activated_path = os.path.join(wit_path, 'activated.txt')
    characters = "1234567890abcdef"
    commit_id = ''.join(random.choices(characters, k=40))
    commit_id_path = os.path.join(wit_path, 'images', commit_id)
    os.makedirs(commit_id_path)
    commit_id_metadata_path = os.path.join(wit_path, 'images', commit_id + '.txt')
    cur_head, cur_master, branches = get_references(references_path)
    create_metadata(cur_head, branch_marge_parent, commit_id_metadata_path, massage)
    staging_area_path = os.path.join(wit_path, 'staging_area')
    shutil.copytree(staging_area_path, commit_id_path, dirs_exist_ok=True)
    active_branch = get_activated(activated_path)
    if not ((cur_head == cur_master and active_branch == 'master')
    or (branches and branches.get(active_branch) == cur_head)):
        active_branch = None
    update_references(references_path, commit_id, active_branch)


def get_new_files(dir_cmp):
    dir_left = dir_cmp.left
    for left_file in dir_cmp.left_only:
        if os.path.isfile(os.path.join(dir_left, left_file)):
            yield left_file
    for sub_dcmp in dir_cmp.subdirs.values():
        yield from get_new_files(sub_dcmp)


def get_different_files(dir_cmp, with_path=False):
    for diff_file in dir_cmp.diff_files:
        if with_path:
            yield os.path.join(dir_cmp.left, diff_file)
        else:
            yield diff_file
    for sub_dcmp in dir_cmp.subdirs.values():
        yield from get_different_files(sub_dcmp, with_path)


def get_changed_files(path1, path2):
    dcmp_commit = filecmp.dircmp(path1, path2)
    return list(get_new_files(dcmp_commit)) + list(get_different_files(dcmp_commit))


def status():
    wit_path = get_wit_path(os.getcwd())
    staging_area_path = os.path.join(wit_path, 'staging_area')
    references_path = os.path.join(wit_path, 'references.txt')
    commit_id = get_references(references_path)[0]
    commit_id_path = os.path.join(wit_path, 'images', commit_id)
    files_to_be_commited = get_changed_files(staging_area_path, commit_id_path)
    files_not_staging = list(get_different_files(filecmp.dircmp(os.path.dirname(wit_path), staging_area_path)))
    files_untracked = list(get_new_files(filecmp.dircmp(os.path.dirname(wit_path), staging_area_path)))
    print(
        f'Commit id: {commit_id}\n'
        f'Changes to be committed: {files_to_be_commited}\n'
        f'Changes not staged for commit: {files_not_staging}\n'
        f'Untracked files: {files_untracked}\n'
    )


def check_possibility(org_path, wit_path, staging_area_path, cur_head):
    head_commit_id = cur_head
    head_commit_id_path = os.path.join(wit_path, 'images', head_commit_id)
    files_to_be_commited = get_changed_files(staging_area_path, head_commit_id_path)
    files_not_staging = list(get_different_files(filecmp.dircmp(org_path, staging_area_path)))
    if files_to_be_commited or files_not_staging:
        raise Exception("Checkout can't be complete")
    return True


def checkout(arg):
    wit_path = get_wit_path(os.getcwd())
    org_path = os.path.dirname(wit_path)
    staging_area_path = os.path.join(wit_path, 'staging_area')
    references_path = os.path.join(wit_path, 'references.txt')
    activated_path = os.path.join(wit_path, 'activated.txt')
    cur_head, cur_master, branches = get_references(references_path)
    if check_possibility(org_path, wit_path, staging_area_path, cur_head):
        if arg == 'master':
            branch_name = arg
            commit_id = cur_master
        elif arg in branches:
            branch_name = arg
            commit_id = branches[branch_name]
        else:
            branch_name = None
            commit_id = arg
        commit_id_path = os.path.join(wit_path, 'images', commit_id)
        shutil.copytree(commit_id_path, org_path, dirs_exist_ok=True)
        update_references(references_path, commit_id)
        shutil.copytree(commit_id_path, staging_area_path, dirs_exist_ok=True)
        update_activated(activated_path, branch_name)


def get_parents(metadata_path):
    with open(metadata_path, 'r') as metadata_file:
        parents = metadata_file.readline().split('=')[1].split(', ')
        parents[-1] = parents[-1].strip()
    if parents[0] == 'None':
        return None
    return parents


def get_parents_dag_from_head(images_path, head):
    current = head
    parents = get_parents(os.path.join(images_path, current + '.txt'))
    if not parents:
        return None
    graph_dict = {current: parents}
    all_parents = set(parents)
    while len(all_parents) > 0:
        currents = all_parents
        all_parents = set()
        for current in currents:
            parents = get_parents(os.path.join(images_path, current + '.txt'))
            if parents:
                graph_dict[current] = parents
                all_parents.update(set(parents))
    return graph_dict


def graph():
    wit_path = get_wit_path(os.getcwd())
    references_path = os.path.join(wit_path, 'references.txt')
    images_path = os.path.join(wit_path, 'images')
    head, master, branches = get_references(references_path)
    graph_dict = get_parents_dag_from_head(images_path, head)
    images_graph = graphviz.Digraph('graph')
    images_graph.attr(rankdir='RL')
    images = []
    if graph_dict:
        for current, parents in graph_dict.items():
            for parent in parents:
                images_graph.edge(current, parent)
                images.extend([current, parents])
    else:
        current = head
        images_graph.node(current)
    images_graph.attr('node', shape='plaintext')
    images_graph.node('head', '')
    images_graph.edge('head', head, label='HEAD')
    if master in images:
        images_graph.node('master', '')
        images_graph.edge('master', master, label='master')
    if branches:
        for branch_name, image in branches.items():
            if image in images:
                images_graph.node(branch_name, '')
                images_graph.edge(branch_name, image, label=branch_name)
    images_graph.view()


def branch(name):
    wit_path = get_wit_path(os.getcwd())
    references_path = os.path.join(wit_path, 'references.txt')
    head = get_references(references_path)[0]
    with open(references_path, 'a') as references_file:
        references_file.write(f"{name}={head}\n")


def get_parents_generations(path, commit):
    current = commit
    parents_generations = [current]
    parents = get_parents(os.path.join(path, current + '.txt'))
    if parents:
        all_parents = set(parents)
        while len(all_parents) > 0:
            currents = all_parents
            all_parents = set()
            parents_generations.extend(currents)
            for current in currents:
                parents = get_parents(os.path.join(path, current + '.txt'))
                if parents:
                    all_parents.update(set(parents))
    return parents_generations


def get_common_commit(path, commit1, commit2):
    for parent1 in get_parents_generations(path, commit1):
        for parent2 in get_parents_generations(path, commit2):
            if parent1 == parent2:
                return parent1


def merge(branch_name):
    wit_path = get_wit_path(os.getcwd())
    staging_area_path = os.path.join(wit_path, 'staging_area')
    references_path = os.path.join(wit_path, 'references.txt')
    images_path = os.path.join(wit_path, 'images')
    head, master, branches = get_references(references_path)
    branch_commit = branches[branch_name]
    common_commit = get_common_commit(images_path, branch_commit, head)
    branch_commit_path = os.path.join(images_path, branch_commit)
    common_commit_path = os.path.join(images_path, common_commit)
    changed_files = get_different_files(filecmp.dircmp(branch_commit_path, common_commit_path), with_path=True)
    for file in changed_files:
        relative_path = os.path.relpath(file, branch_commit_path)
        copy(src_full_path=file, src_relative_path=relative_path, dst_path=staging_area_path)
    commit(f'Marge with {branch_name}', branch_marge_parent=branch_commit)


if __name__ == '__main__':
    #os.chdir('C:/Users/user/PycharmProjects/week10/Etztrubal') #delete
    #init()
    #add('another.txt')
    #add('newstat')
    #add(r'lms\extractors\dev.txt')
    #commit('hi extractor')
    #print(get_changes_to_be_committed(r'C:\Users\user\PycharmProjects\week10\day1\Etztrubal\.wit\staging_area\dev_requirements.txt', r'C:\Users\user\PycharmProjects\week10\day1\Etztrubal\dev_requirements.txt'))
    #dcmp = filecmp.dircmp(r'C:\Users\user\PycharmProjects\week10\day1\Etztrubal\.wit\staging_area', r'C:\Users\user\PycharmProjects\week10\day1\Etztrubal\.wit\images\061a8ede56f491c6857a0ffc49ec9546f7181d9e')
    #print_changes_to_be_committed(dcmp)
    #print(get_changes_to_be_committed(r'C:\Users\user\PycharmProjects\week10\day1\Etztrubal\.wit\staging_area\dev_requirements.txt', r'C:\Users\user\PycharmProjects\week10\day1\Etztrubal\.wit\images\061a8ede56f491c6857a0ffc49ec9546f7181d9e\dev_requirements.txt'))
    #status()
    #print(get_references('C:/Users/user/PycharmProjects/week10/day1/Etztrubal/.wit/references.txt'))
    #checkout('Gili')
    #checkout('Roni')
    #checkout('eff3f52b1b3060fc07c849b870c267dbb7ac9a8e')
    #branch('gili')
    #graph()
    #images_path = r'C:\Users\user\PycharmProjects\week10\Etztrubal\.wit\images'
    #print(get_parents_generations(images_path, '970e30b6334bb6846708749ac3d4e199ba60ad54'))
    #print(get_common_commit(images_path, 'eff3f52b1b3060fc07c849b870c267dbb7ac9a8e', '624da5d85a85420bb4de1b17f5f5f2d682f98035'))
    #marge('Gili')
    #print(get_graph_dict(images_path, 'c4356de8acd5e8d0e33f618bd1d1aca3ebf13455'))
    #print(get_parents(r'C:\Users\user\PycharmProjects\week10\Etztrubal\.wit\images\c4356de8acd5e8d0e33f618bd1d1aca3ebf13455.txt'))

    arg_names = ['file', 'function', 'function_arg']
    args = dict(zip(arg_names, sys.argv))
    functions = {
        'init': init, 'add': add, 'commit': commit,
        'status': status, 'checkout': checkout, 'graph': graph,
        'branch': branch, 'merge': merge
    }
    if 'function' in args:
        if 'function_arg' in args:
            functions[args['function']](args['function_arg'])
        else:
            functions[args['function']]()
