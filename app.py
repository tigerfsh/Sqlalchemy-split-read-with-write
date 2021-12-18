from flask import Flask
from flask import request
from flask import jsonify

from flask_sqlalchemy import SQLAlchemy, SignallingSession, get_state
from sqlalchemy import orm
from sqlalchemy import func 
from sqlalchemy.sql.selectable import Select
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.dml import Delete

from contextlib import contextmanager

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:111@localhost:4406/mydb'  # 设置数据库连接地址
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 是否追踪数据库变化(触发某些钩子函数), 开启后效率会变
app.config['SQLALCHEMY_ECHO'] = True  # 开启后, 控制台会打印底层执行的SQL语句

app.config['SQLALCHEMY_BINDS'] = {  # get_engine的bind参数为该配置的键
    'master': 'mysql+pymysql://root:111@localhost:4406/mydb',
    'slave': 'mysql+pymysql://root:111@localhost:5506/mydb'
}


class RoutingSession(SignallingSession):
    def get_bind(self, mapper=None, clause=None):
        """当进行数据操作时, 会调用该方法来获取进行该操作的数据库引擎(连接)"""
        # print("#"*50)
        # print(f"map: {mapper}")
        # print(f"clause: {clause}, {type(clause)}")
        # print(f"_flushing: {self._flushing}")
        # print("#"*50)

        state = get_state(self.app)
        if self._flushing or isinstance(clause, (Update, Delete)):
        # if self._flushing:  # 增删改操作, 使用主库
            print('使用主库')
            return state.db.get_engine(self.app, bind='master')
        else:  # 读操作, 使用从库
            print('使用从库')
            return state.db.get_engine(self.app, bind='slave')


class RoutingSQLAlchemy(SQLAlchemy):
    def create_session(self, options):
        return orm.sessionmaker(class_=RoutingSession, db=self, **options)

    @contextmanager
    def auto_commit(self):
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e


# 初始化组件(建立数据库连接)
db = RoutingSQLAlchemy(app)


# ORM  类->表  类属性->字段  对象->记录
class User(db.Model):
    __tablename__ = "t_user"  # 设置表名, 默认为类名的小写
    id = db.Column(db.Integer, primary_key=True)  # 主键
    name = db.Column(db.String(20), unique=True, nullable=False)  # 设置唯一&非空约束
    age = db.Column(db.Integer, default=10, index=True)  # 设置默认值约束&建立索引


@app.route('/add', methods=["POST"])
def index():  
    # 增加数据  进行检验是否读写分离
    # 1.创建模型对象
    print(f"{request.json}")
    name = request.json.get("name")
    age = request.json.get("age", 18)
    print(f"{name}: {age}")

    with db.auto_commit():
        user1 = User(name=name, age=int(age))
        db.session.add(user1)

    print('-' * 30)
    # 查询数据  
    print(User.query.all())
    return jsonify(success=True)

@app.route("/update", methods=["POST"])
def update():
    id = request.json.get("id")
    age = request.json.get("age", 18)
    v = request.json.get("v", 1)
    if v == 1:
        if id:
            with db.auto_commit():
                User.query.filter_by(id=id).update({"age": age})
    elif v == 2:
        user = User.query.filter_by(id=id).first()
        with db.auto_commit():
            user.age = age 
            db.session.add(user)

    return jsonify()

@app.route("/del")
def del_obj():
    # 1）物理删除
    # 2）原生的update 

    id = request.args.get("id", type=int)
    with db.auto_commit():
    #     user = User.query.filter_by(id=id).first()
    #     user.age = 1000
    #     db.session.add(user)

        # User.query.filter_by(id=id).update({"age": 55})  # 打在从库
        User.query.filter_by(id=id).delete()  # 打在从库


    
    return jsonify()

@app.route("/list")
def get_all_users():
    # count() vs func.count()
    # print(User.query.count())
    # print(db.session().query(func.count(User.id)).scalar())

    users = User.query.all()
    data = [{"id": user.id, "name": user.name, "age": user.age} for user in users]
    return jsonify(data=data)


if __name__ == '__main__':
    # db.drop_all()  # 删除所有继承自db.Model的表
    # db.create_all()  # 创建所有继承自db.Model的表
    app.run(debug=True)
