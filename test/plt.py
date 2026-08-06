import matplotlib.pyplot as plt
import numpy as np
plt.rcParams['font.sans-serif'] = ['SimHei']  # 或 ['Microsoft YaHei'] 微软雅黑 等
plt.rcParams['axes.unicode_minus'] = False   # 解决负号 '-' 显示为方块的问题
# 数据（对应你的图）
labels = ['林鸿浩', '张勇浩', '冯锦华', '陈宇轩']
sizes = [35, 20, 20, 25]  # 注意：总和要接近100（你的图里数值可能有省略）
colors = ['#8884d8', "#29ce42", "#58ffd5", "#e83821"]

# 绘制环形图
plt.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%', 
        startangle=90, pctdistance=0.85)
# 中间画白色圆，形成环形
centre_circle = plt.Circle((0,0),0.70,fc='black')
fig = plt.gcf()
fig.gca().add_artist(centre_circle)

plt.axis('equal')  # 保证是正圆
plt.show()