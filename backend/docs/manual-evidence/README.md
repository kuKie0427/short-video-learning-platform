# 手工测试执行证据（manual-evidence）

发布冒烟与手工用例的**一手执行留痕**。《手工测试用例-正式版》「实际结果」列引用的编号即本目录文件名。

## 命名与来源

| 类型 | 命名 | 来源 |
| --- | --- | --- |
| UI 截图 | `用例编号-序号.png`（如 `S11-1.png`） | `cd e2e && npm run evidence` 抓取的逐例留痕截图，按用例编号重命名归档 |
| 接口/落库证据 | `YYYY-MM-DD-api-evidence.txt` | curl 与 `backend/scripts/manual_smoke_upload.py` 的原始输出汇总（响应体、SQL 查询行、退出码） |

截图原始产物落在本目录 `raw/`（含 `trace.zip` / `video` ），**`raw/` 不入库**（体积大、可重跑），只归档重命名后的 png 与文本证据。

## 当前留痕清单（2026-09-09 复跑）

| 文件 | 对应用例 | 现场 |
| --- | --- | --- |
| `S02-1.png` | S02 / 快查 S2 | 验证码登录跳转首页 |
| `S04-1.png` | S04 / 快查 S3 | 首页推荐流卡片渲染（封面 + 点赞数） |
| `S09-1.png` | S09 / 快查 S7 | 搜索关键词 → 结果出现 |
| `S10-1.png` | S10 / 快查 S8 | 真实 7.7MB mp4 分片上传 → 完成跳转 |
| `S11-1.png` | S11 / 快查 S9 | direct-split 切分结果页（含 ffmpeg 真实切片） |
| `A01-1.png` | A01 | 非法手机号被前端拦截，验证码输入框不出现 |
| `2026-09-09-api-evidence.txt` | S15 / A06 / U01 / U02 / U09 / R02 / R03 / R04 / R05 / R06 / I01 / P03 / BUG-016 定界 | 接口一手输出 + SQL 落库行 + 网关 502 定界证据 |

## 复核方式

```bash
# UI 类现场可重跑（前置见 e2e/README.md）
cd e2e && npm run evidence

# 接口/落库类现场可重跑（前置：docker-compose up -d 全栈）
cd backend && .venv/bin/python scripts/manual_smoke_upload.py; echo "退出码=$?"

# 看某条 UI 用例的完整 trace（在 raw/ 下，本地保留）
npx playwright show-trace e2e/../backend/docs/manual-evidence/raw/<用例目录>/trace.zip
```

## 规矩

1. **没跑就不打钩**：未执行条目保留 ☐，并在正式版「本轮未执行项与阻塞原因」里写明原因。
2. 失败当天进[缺陷台账](../缺陷台账.md)，编号回填用例「关联缺陷」列，并补一条复现自动化用例。
3. 证据只增不删：每轮发布冒烟新建一个日期文件，不覆写历史留痕。
