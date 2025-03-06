# UDIS2 图像融合系统版本演进说明

---

## 版本概览
| 版本 | 文件名 | 主要改进 | 核心特性          |
|------|--|----------|---------------|
| 1.0 | [gui.py](gui.py) | 基础功能实现 | 单页面操作，同步执行任务  |
| 2.0 | [gui2.py](gui2.py) | 界面分层优化 | 分页布局，图片实时预览   |
| 3.0 | [gui3.py](gui3.py) | 多线程支持 | 异步任务处理，增强日志   |
| 4.0 | [gui4.py](gui4.py) | 流程整合 | 一键式操作，简化代码结构  |
| 5.0 | [gui5.py](gui5.py) | 中间结果展示 | 全流程可视化、展示中间产物 |

---

## 版本详细说明

### 1.0 版本 [gui.py](gui.py)

>ChatGPT提示词:
> 
>你是一名python开发工程师，熟悉GUI开发，熟悉UDIS2图像融合，现在帮我用python实现一个UDIS2图形化的界面，需要仔细思考完成功能如下：
>1. 登陆： 使用ssh连接服务器，用户输入账户类似于：ssh -p 31041 root@cxxxx.com， 密码类似于： abcd 点击登录后开始连接服务器，连接成功后跳转下一步，失败给出提示
>2. 两个选择本地图像的按钮，用户选择输入图片input1和input2，选择成功后，将第一张照片复制到服务器内autodl-tmp/UDIS-D/testing/input1路径下命名为000001.jpg，先将该目录下所有文件清除后再复制，第二张照片复制到autodl-tmp/UDIS-D/testing/input2目录下命名为000001.jpg，也先将该目录下所有文件清除后再复制。复制过程显示出来。
>3. 完成复制后运行python autodl-tmp/UDIS2-main/Warp/Codes/test_output.py 命令，需要一些时间。
>4. 完成后执行python autodl-tmp/UDIS2-main/Composition/Codes/test.py 命令，需要一些时间。
>5. 执行结束后，将服务器中autodl-tmp/UDIS2-main/Composition/composition/000001.jpg文件显示到输出图片的位置。
>6. 整个过程要尽可能的人性化操作，界面整洁美观，操作流程清晰可见。

#### 实现内容
- **基础功能**：支持服务器登录、图片选择、上传、融合任务执行、结果展示。
- **界面设计**：单页面布局，所有功能集中展示。
- **技术实现**：使用 `paramiko` 和 `SCPClient` 实现文件传输，同步执行命令。

#### 存在问题
- **界面卡顿**：所有操作均为同步执行，上传或处理大文件时界面无响应。
- **交互简陋**：图片选择后无预览，日志与功能控件混杂。
- **代码耦合**：功能逻辑与界面代码未分离，维护困难。

#### 优化点（相对初始版本）
- 首个功能完整的基础版本，无历史版本对比。

---

### 2.0 版本 [gui2.py](gui2.py)
>ChatGPT主要提示词::
> 1. 现在需要让登陆和后面的上传融合分成两个页面，登陆成功后再显示第二个页面
> 2. 要反显图片，不是图片路径，界面要优美
#### 实现内容
- **分页布局**：使用 `QStackedWidget` 分离登录页与操作页。
- **图片预览**：支持输入图片的实时预览（并排显示）。
- **代码优化**：通过 `QHBoxLayout` 优化控件布局。

#### 存在问题
- **仍为同步操作**：上传和处理任务阻塞主线程。
- **功能分散**：日志区域与操作按钮布局不够直观。
- **错误处理不足**：未捕获部分异常（如上传失败未回滚）。

#### 优化点（相对 1.0）
- ✅ 分页设计提升用户体验。
- ✅ 图片预览功能增强交互性。
- ✅ 布局代码更清晰。

---

### 3.0 版本 [gui3.py](gui3.py)
>ChatGPT主要提示词::
> 
>好的，继续完成以下修改：
>1. 所有的执行命令等可能耗时的操作都新启一个线程，不要卡顿UI，对于耗时操作可适当增加一下进度提展示。
>2. 去掉上传图片、融合、显示结果的按钮、只保留一个融合操作按钮，点击融合自动执行图片上传、融合、拉去融合结果的操作。
#### 实现内容
- **多线程支持**：使用 `QThread` 分离 SSH 登录、文件上传、融合任务。
- **实时日志**：增加时间戳，支持动态日志刷新。
- **异常处理**：通过信号机制捕获并提示错误。

#### 存在问题
- **线程管理复杂**：多个独立线程增加维护成本。
- **中间结果缺失**：无法查看变形/融合的中间产物。
- **界面冗余**：服务器配置与操作页面仍需切换。

#### 优化点（相对 2.0）
- ✅ 异步操作彻底解决界面卡顿问题。
- ✅ 增强日志可读性（带时间戳）。
- ✅ 错误提示更友好。

---

### 4.0 版本 [gui4.py](gui4.py)
>ChatGPT主要提示词:
> 
> 1. 稳定性优化:使用QThread避免阻塞主线程
> 2. 去掉上传图片和查看结果按钮，点击开始融合就执行原来的 上传图片、开始融合、察看结果的操作、等于是一个按钮代替了原来的三个按钮
#### 实现内容
- **一键式操作**：整合流程（登录+上传+处理+下载）到单一线程。
- **界面简化**：服务器配置与操作界面合并，减少页面跳转。
- **样式优化**：按钮添加 CSS 美化，更符合现代 UI 设计。

#### 存在问题
- **中间结果不可见**：仅展示最终结果，调试不友好。
- **代码耦合度高**：`OperationThread` 类承担过多职责。
- **灵活性差**：无法单独重新上传或重新处理。

#### 优化点（相对 3.0）
- ✅ 流程整合提升操作效率。
- ✅ 界面布局更紧凑。
- ✅ 代码复用率提高。

---

### 5.0 版本 [gui5.py](gui5.py)
>ChatGPT主要提示词:
> 
>继续以下修改：
> - 展示融合中间产物：
> 1. 在执行完成“图像变形处理”后，将服务器中的“autodl-tmp/UDIS-D/testing/mask1/000001.jpg”拉取下来，名字叫mask1，将服务器中的“autodl-tmp/UDIS-D/testing/mask2/000001.jpg”拉取下来，名字叫mask2，将服务器中的“autodl-tmp/UDIS-D/testing/warp1/000001.jpg”拉取下来，名字叫warp1，将服务器中的“autodl-tmp/UDIS-D/testing/warp2/000001.jpg”拉取下来，名字叫warp2，拉取并展示出这四张照片，为这一步的产物，然后继续执行下一步的图像融合处理。
> 2. 在执行完成“图像融合处理”后，将服务器中的“autodl-tmp/UDIS2-main/Composition/learn_mask1/000001.jpg”拉取下来，名字叫learn_mask1，将服务器中的“autodl-tmp/UDIS2-main/Composition/learn_mask2/000001.jpg”拉取下来，名字叫learn_mask2，拉取并展示出这两张照片，为这一步的产物，然后继续执行下一步的拉取展示结果的操作。
#### 实现内容
- **全流程可视化**：展示变形（mask/warp）和融合（learn_mask）的中间结果。
- **布局修复**：使用 `QScrollArea` 和分组框优化展示区域。
- **对象命名规范**：修复控件查找逻辑，增强代码健壮性。

#### 存在问题
- **复杂度高**：界面元素过多，学习成本增加。
- **资源占用**：频繁下载中间文件可能影响性能。
- **依赖固定路径**：服务器文件路径硬编码，灵活性不足。

#### 优化点（相对 4.0）
- ✅ 中间结果可视化，便于调试和分析。
- ✅ 修复布局错乱问题，支持滚动查看。
- ✅ 明确控件命名，减少运行时错误。

---

## 最后
- 实现过程都在上面了，里面有些名称可以改一下，改成专业名词会更好些。
- 布局可以在调整些，本来想价格进度条，但是执行的进度没法预知，没能实现。
- 里面很多命令都是硬编码，尽量不要修改服务器文件位置，需要注意下。
- 轩轩加油哦！