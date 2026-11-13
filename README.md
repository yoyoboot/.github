# Yoyo Boot .github

## Rider 私有源码公共构建

本仓库的 [.github/workflows/rider-build.yml](.github/workflows/rider-build.yml) 接收
`ltm0203/Knight-boss` 的签名 `rider-build-request`，按请求 SHA 只读检出源码，
全量编译并制作 HostApi、SyncJob、Auth、Migrator、Vue、Uni-app H5 六个镜像。
这里不保存 Rider 源码副本、不做 PR 状态回写、不运行自动测试、不部署或执行数据库迁移。

目前为本地实现；文件需要提交到本仓库默认分支并配置 Secrets 后才能远程运行。
私有端也必须提交其 dispatcher、六个 Dockerfile.github 和公网 NuGet.Config，
才能从对应提交构建。请求发送成功不代表镜像已构建成功，实际结果查看本仓库 Actions。

### 接入配置

| 位置 | 类型 / 名称 | 用途 |
| --- | --- | --- |
| 私有 Rider | Secret `PUBLIC_BUILDER_DISPATCH_TOKEN` | 向本仓库发送 repository dispatch；Fine-grained PAT 按 GitHub API 要求授予目标仓库 Contents write，不授权私有源码或 Registry |
| 私有 Rider | Secret `PUBLIC_BUILD_DISPATCH_HMAC_SECRET` | 随机共享签名密钥，建议至少 32 字节 |
| 本仓库 | Secret `RIDER_PRIVATE_SOURCE_PAT` | 仅允许读取 Rider Contents 的 Fine-grained PAT；checkout 不持久保存凭据 |
| 本仓库 | Secret `RIDER_DISPATCH_HMAC_SECRET` | 与私有端 Rider HMAC 密钥相同 |
| 本仓库，可选推送 | Variable `RIDER_IMAGE_REGISTRY` | Registry 主机，不带协议，如 `registry.cn-chengdu.aliyuncs.com` |
| 本仓库，可选推送 | Variable `RIDER_IMAGE_REPOSITORY` | `namespace/repository`，如 `yoyosoft/knightboss` |
| 本仓库，可选推送 | Variable `RIDER_IMAGE_USERNAME` | Registry 登录名 |
| 本仓库，可选推送 | Secret `RIDER_IMAGE_PASSWORD` | Registry 推送凭据，仅 publish 步骤读取 |

所有合法分支均可 push 构建；普通开发分支为 `validate`，不推送。PR 合并到 main（或直接 push main）自动使用 `publish`，编译成功后推送；手动执行仍可明确选择 validate/publish，publish 只允许 main。两端使用 git check-ref-format 校验分支格式，不维护名称白名单；tag 和分支删除不触发构建。目标公共仓库和来源私有仓库固定在代码中，不再配置仓库名 Secret。

签名保持 `yoyoboot-public-build/v4` 的字段布局；Rider 专用策略固定
`build_intent=image`、`build_target=all`，不计算 before/head 差异。
来源、签名、十分钟时间窗或 mode 不正确时，在 checkout 私有源码前失败。
过期请求从私有入口重新运行发送新签名；不要只重跑公共端旧请求。

### 产物和结果

- 公共 runner 将私有 Git 根检出到 `source/`；Docker context 为 `source/`，Dockerfile 为 `source/src/.../Dockerfile.github`。
- 每项的 builder 编译成功后制作运行镜像。矩阵不因单项失败取消其它项，整体摘要准确反映六项结果；某项失败不回滚其它已成功制作/推送的镜像。
- validate 使用临时本地镜像；runner 结束后不保留镜像。publish 发布 `<服务>_main` 固定标签，并同时保留 `<服务>_<私有SHA>-<公共run_id>-<attempt>` 版本标签；main 发布使用独立并发组，取消被新发布替代的旧运行。
- 当前沿用阿里云仓库 `registry.cn-chengdu.aliyuncs.com/yoyosoft/knightboss`。推送不是部署，不改现有测试环境使用的 dev/fix-prod 标签。
- Uni-app 保留 NGINX_WAITHOST/NGINX_WAITPORT（默认 localhost:80）。官方 Nginx 的启动钩子复用 Rider 现有 wait-for-it.sh，在依赖 TCP 就绪后继续原 Nginx 启动流程。
- 保留源码 revision 和 Vue buildId。摘要给出模式、镜像、digest 和实际结果；不将构建成功写成部署或业务测试通过。
- 首版只使用 runner 内 BuildKit 缓存，不向公开仓库导出包含私有源码层的构建缓存，不上传整个 checkout 或 Docker build record。
- 本仓库日志和摘要公开可见，启用前须确认公开范围；不要把真实凭据提交到任一仓库。

本地维护路径是 `D:/new-code/github/.github`，因此工作流路径是
`D:/new-code/github/.github/.github/workflows/rider-build.yml`。
私有端位于 `D:/new-code/github/Knight-boss/.github/workflows/request-public-build.yml`。
两者分别维护、提交和启用，不修改参考 YoyoBoot 仓库。

本地合同回归（需要 Python 3 和 PyYAML，在 Rider Git 根执行）：

```powershell
python src/.github/scripts/testing/test_public_build_runner.py --public-repo ../.github -v
```

这组检查只验证签名收发、分支/推送边界和文件接线，不加入 push 流程，不能替代六镜像真实构建。

欢迎来到 `yoyoboot/.github` 仓库！

## 介绍

这个仓库用于存放 Yoyo Boot 组织的 GitHub 配置文件和模版。通过这个仓库，我们可以集中管理和维护组织的 GitHub 工作流程、Issue 模版、Pull Request 模版等。

## 内容

该仓库包含以下内容：

- **Issue 模版**：用于标准化和简化问题报告流程。
- **Pull Request 模版**：用于规范代码合并请求，确保每个请求都包含必要的信息。
- **GitHub Actions**：自动化 CI/CD 工作流程，用于持续集成和部署。
- **其他配置文件**：包括 CODEOWNERS、CONTRIBUTING 等文件，以帮助维护代码质量和项目协作。

## 使用方法

1. **克隆仓库**：
    ```bash
    git clone https://github.com/yoyoboot/.github.git
    ```

2. **修改配置**：根据项目需求修改相应的配置文件和模版。

3. **提交更改**：
    ```bash
    git add .
    git commit -m "Update GitHub configurations"
    git push origin main
    ```

## 贡献

我们欢迎任何形式的贡献！如果你有任何建议或改进意见，请随时提交 Issue 或 Pull Request。

1. Fork 这个仓库
2. 创建一个新的分支 (`git checkout -b feature-branch`)
3. 提交你的修改 (`git commit -am 'Add some feature'`)
4. 推送到分支 (`git push origin feature-branch`)
5. 创建一个新的 Pull Request

## 联系我们

如果你有任何问题或需要帮助，请通过以下方式联系我们：

- [GitHub Issues](https://github.com/yoyoboot/.github/issues)
- [电子邮件](mailto:support@yoyoboot.com)

感谢你对 Yoyo Boot 的支持！

---

版权所有 © 2025 Yoyo Boot. 保留所有权利。# .github
