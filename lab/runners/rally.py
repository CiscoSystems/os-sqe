from fabric.api import task


@task
def create_task(concurrency, max_vlans, is_single_point):

    n_tenants = int(max_vlans) / 2

    start = n_tenants if is_single_point else 1
    end = n_tenants + 1
    step = 10000 if is_single_point else n_tenants / 10
    with open('configs/rally/scaling.yaml') as f:
        task_body = f.read()
        task_body = task_body.replace('{concurrency}', concurrency)
        task_body = task_body.replace('{n_tenants_start_end_step}', '{0}, {1}, {2}'.format(start, end, step))
    with open('task-rally.yaml', 'w') as f:
        f.write(task_body)
