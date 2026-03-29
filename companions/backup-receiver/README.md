# Backup Receiver

`backup-receiver` 是 Aerisun 备份同步的专用接收器，设计目标是：

- 只接受来自 Tailnet 的单端口流量
- 应用层使用 `Ed25519` 签名验证客户端
- 只允许追加块、清单和提交，不支持远端删除或覆盖历史
- 远端目录同时保留可读的提交树和内部块存储

## 目录结构

接收器写入的数据目录结构如下：

```text
sites/<site_slug>/
  catalog/
    chunks/<aa>/<bb>/<sha256>
    manifests/<sha256>.json
    commit-index/<commit_id>.json
    sessions/<session_id>.json
  commits/YYYY/MM/DD/<timestamp>-<commit_id>/manifest.json
```

## 凭据与允许列表

接收器通过一份 JSON 允许列表识别可写入的客户端公钥：

```json
{
  "my-site": {
    "ed25519_fingerprint_hex": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n"
  }
}
```

环境变量：

- `AERISUN_BACKUP_RECEIVER_DATA_DIR`
- `AERISUN_BACKUP_RECEIVER_KEYS_FILE`
- `AERISUN_BACKUP_RECEIVER_ALLOWED_KEYS_JSON`
- `AERISUN_BACKUP_RECEIVER_ENFORCE_LOCAL_ONLY`
- `AERISUN_BACKUP_RECEIVER_MAX_SKEW_SECONDS`

## 启动

在当前工作树内运行：

```bash
PYTHONPATH=companions/backup-receiver/src \
  AERISUN_BACKUP_RECEIVER_DATA_DIR=/srv/aerisun/backup-receiver \
  AERISUN_BACKUP_RECEIVER_KEYS_FILE=/srv/aerisun/backup-receiver/allowed-keys.json \
  python -m backup_receiver
```

服务默认绑定 `127.0.0.1:9786`，应该由 Tailscale `serve` 对外暴露，而不是直接监听公网。

## Tailscale Serve 示例

```bash
tailscale serve --bg --https=443 127.0.0.1:9786
```

推荐只在接收端打 `tag:aerisun-backup-receiver`，源端打 `tag:aerisun-backup-source`。

## Grants / ACL 示例

```json
{
  "grants": [
    {
      "src": ["tag:aerisun-backup-source"],
      "dst": ["tag:aerisun-backup-receiver:443"]
    }
  ]
}
```

## 说明

- 接收器只做幂等写入和提交发布，不负责远端保留清理。
- 缺失块时会拒绝提交，保证提交目录总是指向完整清单。
- 若部署时启用 `AERISUN_BACKUP_RECEIVER_ENFORCE_LOCAL_ONLY=true`，接收器会拒绝非 loopback 直连，请始终通过 Tailscale `serve` 反代进入。
