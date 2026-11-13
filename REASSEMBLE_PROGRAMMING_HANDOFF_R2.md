# 完整交接包分卷重建说明

GitHub 网页上传在 30 MB 以上时出现间歇性附件登记失败，因此完整交接包改为 20 个无损分卷，每个不超过 30,000,000 字节。请下载全部 `.part01of20` 至 `.part20of20`，按文件名顺序拼接。轻量审查包仍为单一 ZIP。

- 原始文件：`programming_handoff_20261113_r2.zip`
- 原始字节数：595122068
- 原始 SHA256：`efffcfffdf46e573364ceaa1ec454039e7956a7858740dd303f5dfeed4adc8c6`
- 分卷 SHA256：见 `programming_handoff_20261113_r2.parts.sha256`
- 机器清单：见 `GITHUB_ASSET_MANIFEST_R2.json`

PowerShell 重建：

```powershell
$partDir = '.\downloaded-parts'
$outFile = Join-Path $partDir 'programming_handoff_20261113_r2.zip'
$stream = [System.IO.File]::Create($outFile)
try {
  Get-ChildItem $partDir -Filter 'programming_handoff_20261113_r2.zip.part*of20' |
    Sort-Object Name |
    ForEach-Object {
      $input = [System.IO.File]::OpenRead($_.FullName)
      try { $input.CopyTo($stream) } finally { $input.Dispose() }
    }
} finally { $stream.Dispose() }
(Get-FileHash $outFile -Algorithm SHA256).Hash.ToLower()
```

结果必须为 `efffcfffdf46e573364ceaa1ec454039e7956a7858740dd303f5dfeed4adc8c6`。不要在缺失任一分卷时解压；分卷传输失败不代表计算或 ZIP 损坏。
