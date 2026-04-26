from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Project, Task
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///projects.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Создание базы данных
with app.app_context():
    db.create_all()

# Константы для статусов и приоритетов
STATUS_CHOICES = ['Новая', 'В работе', 'На проверке', 'Завершена']
PRIORITY_CHOICES = ['Низкий', 'Средний', 'Высокий']

# ========== МАРШРУТЫ ДЛЯ ПРОЕКТОВ ==========

@app.route('/')
def index():
    """Главная страница - список всех проектов"""
    projects = Project.query.all()
    return render_template('index.html', projects=projects)

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    """Просмотр проекта со списком задач"""
    project = Project.query.get_or_404(project_id)
    tasks = Task.query.filter_by(project_id=project_id).all()
    return render_template('project_detail.html', project=project, tasks=tasks, 
                         STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)

@app.route('/project/create', methods=['GET', 'POST'])
def create_project():
    """Создание нового проекта с задачами"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        tasks_json = request.form.get('tasks_json', '[]')
        
        # Валидация
        if not name or not start_date_str:
            flash('Название и дата начала обязательны!', 'danger')
            return render_template('project_form.html', project=None,
                                 STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = None
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if end_date < start_date:
                flash('Дата окончания не может быть раньше даты начала!', 'danger')
                return render_template('project_form.html', project=None,
                                     STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        # Создаем проект
        project = Project(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(project)
        db.session.flush()  # Получаем ID проекта без коммита
        
        # Создаем задачи из JSON
        tasks_created = 0
        try:
            tasks_data = json.loads(tasks_json)
            for task_data in tasks_data:
                if task_data.get('title'):  # Создаем только задачи с названием
                    task = Task(
                        title=task_data['title'],
                        description=task_data.get('description', ''),
                        status=task_data.get('status', 'Новая'),
                        priority=task_data.get('priority', 'Средний'),
                        assignee=task_data.get('assignee', 'Не назначен'),
                        project_id=project.id
                    )
                    db.session.add(task)
                    tasks_created += 1
        except json.JSONDecodeError:
            flash('Ошибка при обработке задач', 'danger')
            db.session.rollback()
            return render_template('project_form.html', project=None,
                                 STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        db.session.commit()
        flash(f'Проект "{name}" успешно создан с {tasks_created} задачами!', 'success')
        return redirect(url_for('index'))
    
    return render_template('project_form.html', project=None,
                         STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    """Редактирование проекта с возможностью добавления новых задач"""
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        tasks_json = request.form.get('tasks_json', '[]')
        
        if not name or not start_date_str:
            flash('Название и дата начала обязательны!', 'danger')
            return render_template('project_form.html', project=project,
                                 STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = None
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if end_date < start_date:
                flash('Дата окончания не может быть раньше даты начала!', 'danger')
                return render_template('project_form.html', project=project,
                                     STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        # Обновляем информацию о проекте
        project.name = name
        project.description = description
        project.start_date = start_date
        project.end_date = end_date
        
        # Обрабатываем новые задачи из JSON
        try:
            tasks_data = json.loads(tasks_json)
            for task_data in tasks_data:
                # Проверяем, есть ли у задачи ID (существующая задача) или это новая
                task_id = task_data.get('id')
                if task_id:
                    # Обновляем существующую задачу
                    task = Task.query.get(task_id)
                    if task and task.project_id == project.id:
                        task.title = task_data.get('title', '')
                        task.description = task_data.get('description', '')
                        task.status = task_data.get('status', 'Новая')
                        task.priority = task_data.get('priority', 'Средний')
                        task.assignee = task_data.get('assignee', 'Не назначен')
                else:
                    # Создаем новую задачу
                    if task_data.get('title'):  # Создаем только задачи с названием
                        new_task = Task(
                            title=task_data['title'],
                            description=task_data.get('description', ''),
                            status=task_data.get('status', 'Новая'),
                            priority=task_data.get('priority', 'Средний'),
                            assignee=task_data.get('assignee', 'Не назначен'),
                            project_id=project.id
                        )
                        db.session.add(new_task)
        except json.JSONDecodeError as e:
            flash(f'Ошибка при обработке задач: {str(e)}', 'danger')
            db.session.rollback()
            return render_template('project_form.html', project=project,
                                 STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        db.session.commit()
        flash(f'Проект "{name}" успешно обновлён!', 'success')
        return redirect(url_for('index'))
    
    return render_template('project_form.html', project=project,
                         STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
                         
@app.route('/project/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    """Удаление проекта (каскадное удаление всех задач)"""
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('Проект и все его задачи успешно удалены!', 'success')
    return redirect(url_for('index'))

# ========== МАРШРУТЫ ДЛЯ ЗАДАЧ ==========

@app.route('/task/<int:task_id>/toggle', methods=['POST'])
def toggle_task_status(task_id):
    """Переключение статуса задачи (выполнена/не выполнена)"""
    task = Task.query.get_or_404(task_id)
    
    # Переключаем статус между "Завершена" и предыдущим статусом
    if task.status == 'Завершена':
        # Возвращаем в "Новая" или можно сохранить предыдущий статус
        task.status = 'Новая'
        flash(f'Задача "{task.title}" отмечена как невыполненная', 'info')
    else:
        task.status = 'Завершена'
        flash(f'Задача "{task.title}" отмечена как выполненная!', 'success')
    
    db.session.commit()
    
    # Если запрос через AJAX, возвращаем JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        project = Project.query.get(task.project_id)
        return jsonify({
            'success': True,
            'task_id': task.id,
            'new_status': task.status,
            'project_progress': project.get_progress()
        })
    
    return redirect(url_for('project_detail', project_id=task.project_id))

@app.route('/task/<int:task_id>/update-status', methods=['POST'])
def update_task_status(task_id):
    """Обновление статуса задачи из выпадающего списка"""
    task = Task.query.get_or_404(task_id)
    new_status = request.form.get('status')
    
    if new_status in STATUS_CHOICES:
        task.status = new_status
        db.session.commit()
        flash(f'Статус задачи "{task.title}" изменён на "{new_status}"', 'success')
    
    # Если запрос через AJAX, возвращаем JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        project = Project.query.get(task.project_id)
        return jsonify({
            'success': True,
            'task_id': task.id,
            'new_status': task.status,
            'project_progress': project.get_progress()
        })
    
    return redirect(url_for('project_detail', project_id=task.project_id))

@app.route('/project/<int:project_id>/task/create', methods=['GET', 'POST'])
def create_task(project_id):
    """Создание задачи в проекте"""
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        status = request.form.get('status')
        priority = request.form.get('priority')
        assignee = request.form.get('assignee')
        
        if not title or not assignee:
            flash('Название задачи и исполнитель обязательны!', 'danger')
            return render_template('task_form.html', task=None, project=project,
                                 STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        task = Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            assignee=assignee,
            project_id=project_id
        )
        db.session.add(task)
        db.session.commit()
        flash('Задача успешно создана!', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    
    return render_template('task_form.html', task=None, project=project,
                         STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)

@app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
def edit_task(task_id):
    """Редактирование задачи"""
    task = Task.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        status = request.form.get('status')
        priority = request.form.get('priority')
        assignee = request.form.get('assignee')
        
        if not title or not assignee:
            flash('Название задачи и исполнитель обязательны!', 'danger')
            return render_template('task_form.html', task=task, project=project,
                                 STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)
        
        task.title = title
        task.description = description
        task.status = status
        task.priority = priority
        task.assignee = assignee
        db.session.commit()
        flash('Задача успешно обновлена!', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    
    return render_template('task_form.html', task=task, project=project,
                         STATUS_CHOICES=STATUS_CHOICES, PRIORITY_CHOICES=PRIORITY_CHOICES)

@app.route('/task/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    """Удаление задачи"""
    task = Task.query.get_or_404(task_id)
    project_id = task.project_id
    
    db.session.delete(task)
    db.session.commit()
    flash('Задача успешно удалена!', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

if __name__ == '__main__':
    app.run(debug=True, port=5000)