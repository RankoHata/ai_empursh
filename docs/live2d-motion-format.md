# Cubism 5 Motion 文件格式参考

> 基于 Cubism SDK for Web 5-r.5 源码逆向分析，用于编写自定义 motion 文件。
> **注：** motion 文件格式为 Version 3，这是 Cubism 3/4/5 通用的最新版。SDK 版本号（5）不等于 motion 格式版本号（3）。

---

## 1. 文件结构

```json
{
  "Version": 3,
  "Meta": {
    "Duration": 8.867,
    "Fps": 30.0,
    "Loop": true,
    "AreBeziersRestricted": true,
    "CurveCount": 29,
    "TotalSegmentCount": 1150,
    "TotalPointCount": 1150,
    "UserDataCount": 0,
    "TotalUserDataSize": 0
  },
  "Curves": [...],
  "UserData": []
}
```

### Meta 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `Duration` | float | 动画总时长（秒） |
| `Fps` | float | 帧率，通常 30.0 |
| `Loop` | bool | 是否循环（Cubism 5 不再解析此字段，需代码设 `setLoop(true)`） |
| `AreBeziersRestricted` | bool | 贝塞尔控制点使用受限格式，通常 true |
| `CurveCount` | int | 曲线数量，等于 `Curves` 数组长度 |
| `TotalSegmentCount` | int | **所有曲线的段总数，必须 ≥ 实际段数，否则解析崩溃** |
| `TotalPointCount` | int | **所有曲线的点总数，必须 ≥ 实际点数** |
| `UserDataCount` | int | 用户数据条目数 |
| `TotalUserDataSize` | int | 用户数据总大小 |

**关键：** `TotalSegmentCount` 和 `TotalPointCount` 用于预分配数组。如果小于实际值，解析器会访问越界导致 `Cannot set properties of undefined` 崩溃。**必须精确匹配实际段数！** Cubism 5 的 `cubismmotionjson.ts` 在解析后会校验 `actualTotalSegmentCount == Meta.TotalSegmentCount`，不匹配触发 `CSM_ASSERT`。单个 motion 不匹配只打印警告，但加载多个 motion 时断言可能导致后续解析崩溃。因此 **TotalSegmentCount 和 TotalPointCount 必须精确等于实际值**。

---

## 2. Curves — 曲线数据

每个曲线控制模型的一个参数：

```json
{
  "Target": "Parameter",
  "Id": "ParamAngleX",
  "Segments": [0, 0, 1, 0.333, -5.15, 0.667, -23, 1, ...]
}
```

| 字段 | 说明 |
|------|------|
| `Target` | `"Parameter"`（控制模型参数）或 `"Model"`（控制模型级属性如透明度）。Cubism 5 两种都支持 |
| `Id` | 参数 ID，如 `ParamAngleX`、`ParamEyeLOpen`。**必须与模型的参数列表匹配** |
| `Segments` | 扁平的数值数组，交替存储时间和值 |

---

## 3. Segments 解析算法

### 3.1 数据布局

Cubism 解析器从 `Segments` 扁平数组中按顺序读取，格式如下：

```
[P0_t, P0_v, type_1, P1_t, P1_v, type_2, P2_t, P2_v, ...]

（对于 Bezier 段，每个段有 2 个控制点而非 1 个）
```

### 3.2 解析循环（伪代码）

```
pos = 0

// 1. 读取起点 P0
P0 = (Segments[0], Segments[1])
points.add(P0)
pos = 2

// 2. 循环读取段
while pos < len(Segments):
    type = Segments[pos]  // 段类型

    if type == 0:   // LINEAR 段
        // 读取 1 个控制点（终点）
        P1 = (Segments[pos+1], Segments[pos+2])
        points.add(P1)
        pos += 3  // type + 2 values

    if type == 1:   // BEZIER 段
        // 读取 2 个控制点
        P1 = (Segments[pos+1], Segments[pos+2])  // 第一个控制点
        P2 = (Segments[pos+3], Segments[pos+4])  // 第二个控制点
        points.add(P1)
        points.add(P2)
        pos += 5  // type + 4 values

    if type == 2:   // STEPPED 段
        // 类似于 Linear，但不插值
        P1 = (Segments[pos+1], Segments[pos+2])
        points.add(P1)
        pos += 3

    if type == 3:   // INVERSE_STEPPED 段
        P1 = (Segments[pos+1], Segments[pos+2])
        points.add(P1)
        pos += 3

    segmentCount += 1
```

### 3.3 段类型枚举

| 值 | 类型 | 每个段追加的控制点数量 |
|----|------|---------------------|
| 0 | Linear | 1 个点（2 个值） |
| 1 | Bezier | 2 个点（4 个值） |
| 2 | Stepped | 1 个点（2 个值） |
| 3 | InverseStepped | 1 个点（2 个值） |

### 3.4 Bezier 段的 4 点结构

一个 Bezier 段实际上使用 **4 个点**（P0, P1, P2, P3），但数据中只显式存储 P1 和 P2：

- **P0** = 前一段的最后一个控制点（或起点）
- **P1** = 当前段的首个控制点（影响出射切线）
- **P2** = 当前段的次个控制点（影响入射切线）
- **P3** = 下一段的首个控制点（即下一段的 P0）

段与段之间共享边界点，形成连续的贝塞尔曲线链。

---

## 4. 曲线求值算法

### 4.1 段查找（`evaluateCurve`）

```
function evaluateCurve(time):
    for each segment:
        pointPosition = segment.basePointIndex + (bezier ? 3 : 1)
        if points[pointPosition].time > time:
            return segment.evaluate(points, time)
    // time 超出所有段
    if isCorrection && time < endTime:
        return correctEndPoint(...)
    return points[last].value
```

### 4.2 Linear 求值（`linearEvaluate`）

```
function linearEvaluate(points, time):
    t = (time - P0.t) / (P1.t - P0.t)
    return P0.v + t * (P1.v - P0.v)
```

### 4.3 Bezier 求值（`bezierEvaluate`，De Casteljau 算法）

```
function bezierEvaluate(points[4], time):
    t = (time - P0.t) / (P3.t - P0.t)
    if t < 0: t = 0
    if t > 1: t = 1

    p01 = lerp(P0, P1, t)
    p12 = lerp(P1, P2, t)
    p23 = lerp(P2, P3, t)

    p012 = lerp(p01, p12, t)
    p123 = lerp(p12, p23, t)

    return lerp(p012, p123, t).value
```

**注意：** 只有 P0.t 和 P3.t 参与时间参数化。P1.t 和 P2.t 的时间值只影响曲线形状（通过 De Casteljau），不影响 t 的计算。

### 4.4 循环边界处理（`correctEndPoint`）

当 `MotionBehavior_V2 && isLoop` 时，duration 被延长 1 帧（`1/fps` 秒）。这段时间内，求值走 `correctEndPoint` 路径：

```
function correctEndPoint(P_last, P_first, time, endTime):
    // 创建线性段：[P_last → (endTime, P_first.value)]
    segment[0] = (P_last.t, P_last.v)
    segment[1] = (endTime, P_first.v)
    return linearEvaluate(segment, time)
```

---

## 5. 编写自定义 Motion 文件

### 5.1 最小有效文件

```json
{
  "Version": 3,
  "Meta": {
    "Duration": 3.0,
    "Fps": 30.0,
    "Loop": true,
    "AreBeziersRestricted": true,
    "CurveCount": 1,
    "TotalSegmentCount": 100,
    "TotalPointCount": 100,
    "UserDataCount": 0,
    "TotalUserDataSize": 0
  },
  "Curves": [
    {
      "Target": "Parameter",
      "Id": "ParamAngleX",
      "Segments": [
        0, 0,
        0, 1.5, 5,
        0, 3.0, 0
      ]
    }
  ],
  "UserData": []
}
```

Segments 解读：
- P0: (t=0, v=0)
- Linear 段: type=0, P1: (t=1.5, v=5) — 从 0 线性过渡到 5
- Linear 段: type=0, P1: (t=3.0, v=0) — 从 5 线性过渡回 0

### 5.2 循环无缝要求

1. **首尾值必须相等**：所有曲线的 `Segments[1] == Segments[-1]`
2. **时间必须覆盖全程**：第一点 t=0，最后一点 t=Duration
3. **TotalSegmentCount ≥ 实际段数**：安全取 `len(Segments)` 或更大
4. **Bezier 段使用受限格式（`AreBeziersRestricted: true`）**

### 5.3 可用参数 ID

标准 Cubism 参数（大部分模型都有）：

| 参数 | 说明 |
|------|------|
| `ParamAngleX` | 身体左右倾斜 |
| `ParamAngleY` | 身体前后倾斜 |
| `ParamAngleZ` | 头部左右旋转 |
| `ParamBodyAngleX` | 身体左右旋转 |
| `ParamBodyAngleY` | 身体前后旋转 |
| `ParamBodyAngleZ` | 身体左右倾斜 |
| `ParamEyeLOpen` | 左眼开合 |
| `ParamEyeROpen` | 右眼开合 |
| `ParamEyeBallX` | 眼球 X 位置 |
| `ParamEyeBallY` | 眼球 Y 位置 |
| `ParamBrowLY` | 左眉 Y |
| `ParamBrowRY` | 右眉 Y |
| `ParamMouthOpenY` | 嘴张开 |
| `ParamMouthForm` | 嘴型 |
| `ParamBreath` | 呼吸 |

### 5.4 代码中必调 API

```typescript
const motion = this.loadMotion(buffer, buffer.byteLength, groupName);
motion.setEffectIds(
    [CubismDefaultParameterId.ParamEyeLOpen, CubismDefaultParameterId.ParamEyeROpen],
    [CubismDefaultParameterId.ParamMouthOpenY]
);
motion.setLoop(true);
motion.setLoopFadeIn(true);
motion.setMotionBehavior(2);  // MotionBehavior_V2
```

---

## 6. 已知陷阱

1. **Meta 计数错误** → 解析器崩溃。推荐设 1150 安全值（比实际大即可，精确值容易算错）。
2. **Meta 必须大于实际** → Cubism 5 会校验但设为 1150 对所有模型都安全。设精确值反而容易算错导致越界。
3. **Cubism 5 同 group 不支持多个 motion** → 加载第二个 motion 时解析器内部状态冲突崩溃。model3.json 的每个 group 只能放一个 motion。
4. **`setEffectIds` 签名为数组** → 传单值而非数组导致 `_eyeBlinkParameterIds` 为 undefined。正确：`setEffectIds([EyeLOpen,EyeROpen], [MouthOpenY])`。
5. **Cubism 5 不解析 JSON 的 `Loop` 字段** → 必须 `motion.setLoop(true)`。源码 `cubismmotion.ts:348` 注释掉了 `_loop` 赋值。
6. **三个必须的代码设置** → `setLoop(true)` + `setLoopFadeIn(true)` + `setMotionBehavior(2)`，缺一就崩溃或不循环。
7. **Bezier 控制点的 t 值可能为负数** → 这是正常的，用于 "受限贝塞尔" 编码。
8. **`correctEndPoint` 永远产生线性过渡** → 非贝塞尔。首尾值对齐时平滑，不对齐时有速度突变。
9. **G36/Cubism 3 模型常见问题** → Meta 计数偏小导致崩溃（必须修）；paramopai 透明度曲线首尾值不匹配导致循环不流畅（不修也能跑）。
10. **`TotalSegmentCount`/`TotalPointCount` 必须精确匹配** → 自定义 motion 需要精确计算。安全值对原始模型可行但对自写 motion 可能触发 CSM_ASSERT。
