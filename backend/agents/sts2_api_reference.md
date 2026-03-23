# STS2 反编译 API 参考

> 自动生成，来源：sts2.dll 反编译（ilspycmd v9.1.0）
> 只保留签名，不含方法体实现
> 游戏路径：见 config.json `sts2_path` 字段

## ⚡ 完整反编译源码（优先用这里，不要跑 ilspycmd）

反编译目录路径由 `config.json` 的 `decompiled_src_path` 字段配置，已在你的 prompt 的 **API Lookup** 段注入。
若该段显示"NOT available"，运行 `python tools/decompile_sts2.py --game-path <STS2路径>` 生成。

常用子目录（在配置的反编译目录下）：
```
MegaCrit.Sts2.Core.Commands\      ← DamageCmd, CardCmd, CardSelectCmd, RelicSelectCmd, PowerCmd...
MegaCrit.Sts2.Core.Models.Cards\  ← StrikeIronclad, 所有原版卡牌完整实现
MegaCrit.Sts2.Core.Models\        ← AbstractModel, RelicModel, CardModel, ModelDb
MegaCrit.Sts2.Core.Entities.Players\   ← Player
MegaCrit.Sts2.Core.CardSelection\      ← CardSelectorPrefs
```

只有在反编译目录里找不到时才用 ilspycmd。

---

## 官方参照实现（直接抄，不用反编译）

### Attack 卡标准实现 — StrikeIronclad（原版基础攻击卡）

```csharp
// 来源：sts2.dll MegaCrit.Sts2.Core.Models.Cards.StrikeIronclad（完整实现）
using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;                 // DamageCmd
using MegaCrit.Sts2.Core.Entities.Cards;           // CardType, CardRarity, TargetType, CardTag
using MegaCrit.Sts2.Core.GameActions.Multiplayer;  // PlayerChoiceContext, CardPlay
using MegaCrit.Sts2.Core.Localization.DynamicVars; // DamageVar
using MegaCrit.Sts2.Core.ValueProps;               // ValueProp

namespace MegaCrit.Sts2.Core.Models.Cards;

public sealed class StrikeIronclad : CardModel
{
    protected override HashSet<CardTag> CanonicalTags => new HashSet<CardTag> { CardTag.Strike };

    // DamageVar(baseValue, ValueProp.Move) — 伤害值，跟随力量/虚弱/脆弱自动计算
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new DamageVar(6m, ValueProp.Move)];

    public StrikeIronclad()
        : base(1, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        ArgumentNullException.ThrowIfNull(cardPlay.Target, "cardPlay.Target");
        await DamageCmd.Attack(base.DynamicVars.Damage.BaseValue)
            .FromCard(this)
            .Targeting(cardPlay.Target)
            .WithHitFx("vfx/vfx_attack_slash")   // 可选：命中特效
            .Execute(choiceContext);
    }

    protected override void OnUpgrade()
    {
        base.DynamicVars.Damage.UpgradeValueBy(3m);  // 6 → 9
    }
}
```

**关键模式：**
- `CanonicalVars` 声明伤害值 → 引擎自动显示在卡牌描述里
- `DamageCmd.Attack(value).FromCard(this).Targeting(target).Execute(ctx)` — 标准单目标攻击链
- `base.DynamicVars.Damage.BaseValue` — 读取已计算伤害（含 Strength 加成）
- `.WithHitFx(...)` — 可选命中特效，不加也能正常造伤害
- `OnUpgrade()` 里用 `UpgradeValueBy(delta)` 而不是直接赋值

### CustomRelicModel 标准实现（BaseLib，含自动注册）

```csharp
// BaseLib.Abstracts.CustomRelicModel 源码（核心部分）
// 注意：构造器会自动调用 CustomContentDictionary.AddModel() 完成注册
// 配合 [Pool(typeof(SharedRelicPool))] 即可进入遗物奖励池，无需 Harmony patch

public abstract class CustomRelicModel : RelicModel, ICustomModel
{
    public CustomRelicModel(bool autoAdd = true)
    {
        if (autoAdd)
            CustomContentDictionary.AddModel(this.GetType());  // 自动注册
    }
    public virtual RelicModel? GetUpgradeReplacement() => null;
}
```

---

## 命名空间概览

| 命名空间 | 内容 |
|---|---|
| `MegaCrit.Sts2.Core.Models` | RelicModel, CardModel, PowerModel, ModelDb, AbstractModel |
| `MegaCrit.Sts2.Core.Entities.Players` | Player |
| `MegaCrit.Sts2.Core.Entities.Creatures` | Creature, DamageResult |
| `MegaCrit.Sts2.Core.Entities.Cards` | PileType, CardRarity, CardType, TargetType |
| `MegaCrit.Sts2.Core.Entities.Relics` | RelicRarity |
| `MegaCrit.Sts2.Core.Entities.Powers` | PowerType, PowerStackType |
| `MegaCrit.Sts2.Core.Commands` | CardCmd |
| `MegaCrit.Sts2.Core.Models.RelicPools` | SharedRelicPool |
| `MegaCrit.Sts2.Core.GameActions.Multiplayer` | PlayerChoiceContext |

---

## AbstractModel（所有 model 的基类）

```csharp
namespace MegaCrit.Sts2.Core.Models;

public abstract class AbstractModel : IComparable<AbstractModel>
{
    public ModelId Id { get; }
    public bool IsMutable { get; }
    public virtual bool PreviewOutsideOfCombat => false;
    public abstract bool ShouldReceiveCombatHooks { get; }

    // 克隆
    protected virtual void DeepCloneFields()
    protected virtual void AfterCloned()

    // ========== 战斗 Hook（Task 返回）==========
    // 所有 hook 默认返回 Task.CompletedTask，override 后异步执行

    // 遭遇/行动
    public virtual Task AfterActEntered()
    public virtual Task BeforeRoomEntered(AbstractRoom room)
    public virtual Task AfterRoomEntered(AbstractRoom room)

    // 卡牌相关
    public virtual Task AfterAddToDeckPrevented(CardModel card)
    public virtual Task AfterCardChangedPiles(CardModel card, PileType oldPileType, AbstractModel? source)
    public virtual Task AfterCardChangedPilesLate(CardModel card, PileType oldPileType, AbstractModel? source)
    public virtual Task AfterCardDiscarded(PlayerChoiceContext choiceContext, CardModel card)
    public virtual Task AfterCardDrawnEarly(PlayerChoiceContext choiceContext, CardModel card, bool fromHandDraw)
    public virtual Task AfterCardDrawn(PlayerChoiceContext choiceContext, CardModel card, bool fromHandDraw)
    public virtual Task AfterCardEnteredCombat(CardModel card)
    public virtual Task AfterCardGeneratedForCombat(CardModel card, bool addedByPlayer)
    public virtual Task AfterCardExhausted(PlayerChoiceContext choiceContext, CardModel card, bool causedByEthereal)
    public virtual Task BeforeCardAutoPlayed(CardModel card, Creature? target, AutoPlayType type)
    public virtual Task BeforeCardPlayed(CardPlay cardPlay)
    public virtual Task AfterCardPlayed(PlayerChoiceContext context, CardPlay cardPlay)
    public virtual Task AfterCardPlayedLate(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    public virtual Task AfterCardRetained(CardModel card)
    public virtual Task BeforeCardRemoved(CardModel card)

    // 战斗开始/结束
    public virtual Task BeforeCombatStart()
    public virtual Task BeforeCombatStartLate()
    public virtual Task AfterCombatEnd(CombatRoom room)
    public virtual Task AfterCombatVictoryEarly(CombatRoom room)
    public virtual Task AfterCombatVictory(CombatRoom room)

    // 生物相关
    public virtual Task AfterCreatureAddedToCombat(Creature creature)
    public virtual Task AfterCurrentHpChanged(Creature creature, decimal delta)
    public virtual Task BeforeDeath(Creature creature)
    public virtual Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature, bool wasRemovalPrevented, float deathAnimLength)
    public virtual Task AfterDiedToDoom(PlayerChoiceContext choiceContext, IReadOnlyList<Creature> creatures)

    // 攻击/伤害
    public virtual Task BeforeAttack(AttackCommand command)
    public virtual Task AfterAttack(AttackCommand command)
    public virtual Task AfterDamageGiven(PlayerChoiceContext choiceContext, Creature? dealer, DamageResult result, ValueProp props, Creature target, CardModel? cardSource)
    public virtual Task BeforeDamageReceived(PlayerChoiceContext choiceContext, Creature target, decimal amount, ValueProp props, Creature? dealer, CardModel? cardSource)
    public virtual Task AfterDamageReceived(PlayerChoiceContext choiceContext, Creature target, DamageResult result, ValueProp props, Creature? dealer, CardModel? cardSource)
    public virtual Task AfterDamageReceivedLate(PlayerChoiceContext choiceContext, Creature target, DamageResult result, ValueProp props, Creature? dealer, CardModel? cardSource)

    // 护盾
    public virtual Task AfterBlockCleared(Creature creature)
    public virtual Task BeforeBlockGained(Creature creature, decimal amount, ValueProp props, CardModel? cardSource)
    public virtual Task AfterBlockGained(Creature creature, decimal amount, ValueProp props, CardModel? cardSource)
    public virtual Task AfterBlockBroken(Creature creature)
    public virtual Task AfterModifyingBlockAmount(decimal modifiedAmount, CardModel? cardSource, CardPlay? cardPlay)

    // 能量 / 星星
    public virtual Task AfterEnergyReset(Player player)
    public virtual Task AfterEnergyResetLate(Player player)
    public virtual Task AfterEnergySpent(CardModel card, int amount)
    public virtual Task AfterStarsSpent(int amount, Player spender)
    public virtual Task AfterStarsGained(int amount, Player gainer)

    // 回合
    public virtual Task BeforeSideTurnStart(PlayerChoiceContext choiceContext, CombatSide side, CombatState combatState)
    public virtual Task AfterSideTurnStart(CombatSide side, CombatState combatState)
    public virtual Task AfterPlayerTurnStartEarly(PlayerChoiceContext choiceContext, Player player)
    public virtual Task AfterPlayerTurnStart(PlayerChoiceContext choiceContext, Player player)
    public virtual Task AfterPlayerTurnStartLate(PlayerChoiceContext choiceContext, Player player)
    public virtual Task BeforePlayPhaseStart(PlayerChoiceContext choiceContext, Player player)
    public virtual Task BeforeTurnEndVeryEarly(PlayerChoiceContext choiceContext, CombatSide side)
    public virtual Task BeforeTurnEndEarly(PlayerChoiceContext choiceContext, CombatSide side)
    public virtual Task BeforeTurnEnd(PlayerChoiceContext choiceContext, CombatSide side)
    public virtual Task AfterTurnEnd(PlayerChoiceContext choiceContext, CombatSide side)
    public virtual Task AfterTurnEndLate(PlayerChoiceContext choiceContext, CombatSide side)

    // 抽牌阶段
    public virtual Task BeforeFlush(PlayerChoiceContext choiceContext, Player player)
    public virtual Task BeforeFlushLate(PlayerChoiceContext choiceContext, Player player)
    public virtual Task BeforeHandDraw(Player player, PlayerChoiceContext choiceContext, CombatState combatState)
    public virtual Task BeforeHandDrawLate(Player player, PlayerChoiceContext choiceContext, CombatState combatState)
    public virtual Task AfterHandEmptied(PlayerChoiceContext choiceContext, Player player)

    // 其他战斗
    public virtual Task AfterShuffle(PlayerChoiceContext choiceContext, Player shuffler)
    public virtual Task AfterSummon(PlayerChoiceContext choiceContext, Player summoner, decimal amount)
    public virtual Task AfterTakingExtraTurn(Player player)
    public virtual Task AfterTargetingBlockedVfx(Creature blocker)
    public virtual Task AfterForge(decimal amount, Player forger, AbstractModel? source)
    public virtual Task AfterModifyingCardPlayCount(CardModel card)
    public virtual Task AfterModifyingCardPlayResultPileOrPosition(CardModel card, PileType pileType, CardPilePosition position)

    // 商店 / 奖励 / 地图
    public virtual Task AfterGoldGained(Player player)
    public virtual Task AfterItemPurchased(Player player, MerchantEntry itemPurchased, int goldSpent)
    public virtual Task AfterMapGenerated(ActMap map, int actIndex)

    // ========== 修改器 Hook（返回 int/bool/void）==========
    public virtual int ModifyAttackHitCount(AttackCommand attack, int hitCount)
    public virtual int ModifyCardPlayCount(CardModel card, Creature? target, int playCount)
    public virtual int ModifyOrbPassiveTriggerCounts(OrbModel orb, int triggerCount)
    public virtual int ModifyXValue(CardModel card, int originalValue)
    public virtual void ModifyMerchantCardCreationResults(Player player, List<CardCreationResult> cards)
    public virtual void ModifyShuffleOrder(Player player, List<CardModel> cards, bool isInitialShuffle)

    // TryModify 系列（返回 true 表示已修改）
    public virtual bool TryModifyCardBeingAddedToDeck(CardModel card, out CardModel? newCard)
    public virtual bool TryModifyCardBeingAddedToDeckLate(CardModel card, out CardModel? newCard)
    public virtual bool TryModifyCardRewardAlternatives(Player player, CardReward cardReward, List<CardRewardAlternative> alternatives)
    public virtual bool TryModifyCardRewardOptions(Player player, List<CardCreationResult> cardRewardOptions, CardCreationOptions creationOptions)
    public virtual bool TryModifyCardRewardOptionsLate(Player player, List<CardCreationResult> cardRewardOptions, CardCreationOptions creationOptions)
    public virtual bool TryModifyEnergyCostInCombat(CardModel card, decimal originalCost, out decimal modifiedCost)
    public virtual bool TryModifyStarCost(CardModel card, decimal originalCost, out decimal modifiedCost)
    public virtual bool TryModifyPowerAmountReceived(PowerModel canonicalPower, Creature target, decimal amount, Creature? applier, out decimal modifiedAmount)
    public virtual bool TryModifyRestSiteOptions(Player player, ICollection<RestSiteOption> options)
    public virtual bool TryModifyRestSiteHealRewards(Player player, List<Reward> rewards, bool isMimicked)
    public virtual bool TryModifyRewards(Player player, List<Reward> rewards, AbstractRoom? room)
    public virtual bool TryModifyRewardsLate(Player player, List<Reward> rewards, AbstractRoom? room)

    // Should 系列（条件拦截，返回 false 阻止行为）
    public virtual bool ShouldAddToDeck(CardModel card)
    public virtual bool ShouldAfflict(CardModel card, AfflictionModel affliction)
    public virtual bool ShouldAllowAncient(Player player, AncientEventModel ancient)
    public virtual bool ShouldAllowHitting(Creature creature)
    public virtual bool ShouldAllowTargeting(Creature target)
    public virtual bool ShouldAllowSelectingMoreCardRewards(Player player, CardReward cardReward)
    public virtual bool ShouldClearBlock(Creature creature)
    public virtual bool ShouldDie(Creature creature)
    public virtual bool ShouldDieLate(Creature creature)
    public virtual bool ShouldDisableRemainingRestSiteOptions(Player player)
    public virtual bool ShouldDraw(Player player, bool fromHandDraw)
    public virtual bool ShouldEtherealTrigger(CardModel card)
    public virtual bool ShouldFlush(Player player)
    public virtual bool ShouldGainGold(decimal amount, Player player)
    public virtual bool ShouldGainStars(decimal amount, Player player)
    public virtual bool ShouldGenerateTreasure(Player player)
    public virtual bool ShouldPayExcessEnergyCostWithStars(Player player)
    public virtual bool ShouldPlay(CardModel card, AutoPlayType autoPlayType)
    public virtual bool ShouldPlayerResetEnergy(Player player)
    public virtual bool ShouldProceedToNextMapPoint()
    public virtual bool ShouldProcurePotion(PotionModel potion, Player player)
    public virtual bool ShouldPowerBeRemovedOnDeath(PowerModel power)
    public virtual bool ShouldRefillMerchantEntry(MerchantEntry entry, Player player)
    public virtual bool ShouldAllowMerchantCardRemoval(Player player)
    public virtual bool ShouldCreatureBeRemovedFromCombatAfterDeath(Creature creature)
    public virtual bool ShouldStopCombatFromEnding()
    public virtual bool ShouldTakeExtraTurn(Player player)
    public virtual bool ShouldForcePotionReward(Player player, RoomType roomType)
}
```

---

## RelicModel

```csharp
namespace MegaCrit.Sts2.Core.Models;

// 继承自 AbstractModel（获得所有战斗 hook）
public abstract class RelicModel : AbstractModel
{
    // 必须实现
    public abstract RelicRarity Rarity { get; }

    // 重要继承：
    public override bool ShouldReceiveCombatHooks => true;

    // 所有者
    public Player Owner { get; set; }

    // 状态
    public RelicStatus Status { get; set; }   // Normal / Active / Disabled
    public bool IsWax { get; set; }
    public bool IsMelted { get; set; }
    public int FloorAddedToDeck { get; set; }
    public int StackCount { get; private set; }

    // 虚属性（可 override）
    public virtual bool IsUsedUp => false;
    public virtual bool HasUponPickupEffect => false;
    public virtual bool SpawnsPets => false;
    public virtual bool IsStackable => false;
    public virtual bool AddsPet => false;
    public virtual bool ShowCounter => false;
    public virtual int DisplayAmount => 0;
    public virtual string FlashSfx => "event:/sfx/ui/relic_activate_general";
    public virtual bool ShouldFlashOnPlayer => true;
    public virtual int MerchantCost { get; }

    // 本地化 (key = "relics")
    public virtual LocString Title { get; }
    public LocString Description { get; }
    public LocString Flavor { get; }
    public LocString DynamicDescription { get; }

    // 图标路径
    public virtual string PackedIconPath { get; }
    protected virtual string BigIconPath { get; }

    // 生命周期 Hook
    public virtual Task AfterObtained()
    public virtual Task AfterRemoved()
    public virtual bool IsAllowed(IRunState runState)

    // 动画
    public void Flash()
    public void Flash(IEnumerable<Creature> targets)

    // 序列化
    public RelicModel ToMutable()
    public SerializableRelic ToSerializable()
    public static RelicModel FromSerializable(SerializableRelic save)

    // 事件
    public event Action<RelicModel, IEnumerable<Creature>>? Flashed;
    public event Action? DisplayAmountChanged;
    public event Action? StatusChanged;

    // 动态变量
    public DynamicVarSet DynamicVars { get; }
    protected virtual IEnumerable<DynamicVar> CanonicalVars => Array.Empty<DynamicVar>();
}
```

**注意：** STS2 中遗物直接继承 `RelicModel`（不通过 BaseLib 的中间类），通过 override `AbstractModel` 的 hook 方法实现效果。

---

## CardModel

```csharp
namespace MegaCrit.Sts2.Core.Models;

// 继承自 AbstractModel（获得所有战斗 hook）
public abstract class CardModel : AbstractModel
{
    // 必须实现（或由 BaseLib 的 CustomCardModel 提供默认值）
    public virtual CardType Type { get; }
    public virtual CardRarity Rarity { get; }
    public virtual TargetType TargetType { get; }
    protected virtual int CanonicalEnergyCost { get; }

    // 重要继承：
    public override bool ShouldReceiveCombatHooks => Pile?.IsCombatPile ?? false;

    // 所有者
    public Player? Owner { get; set; }

    // 费用
    public CardEnergyCost EnergyCost { get; }
    protected virtual bool HasEnergyCostX => false;
    public virtual int CanonicalStarCost => -1;
    public virtual int CurrentStarCost { get; }
    public virtual bool HasStarCostX => false;
    public int LastStarsSpent { get; set; }

    // 升级
    public virtual int MaxUpgradeLevel => 1;
    public int UpgradeLevel { get; set; }

    // 池 / 分类
    public virtual CardPoolModel Pool { get; }
    public virtual CardMultiplayerConstraint MultiplayerConstraint => CardMultiplayerConstraint.None;

    // 关键词 / 标签
    public virtual IEnumerable<CardKeyword> CanonicalKeywords => Array.Empty<CardKeyword>();
    public virtual IEnumerable<CardTag> Tags { get; }
    protected virtual HashSet<CardTag> CanonicalTags => new HashSet<CardTag>();

    // 行为标志
    public virtual bool CanBeGeneratedInCombat => true;
    public virtual bool CanBeGeneratedByModifiers => true;
    public virtual bool GainsBlock => false;
    public virtual bool HasTurnEndInHandEffect => false;
    public virtual bool HasBuiltInOverlay => false;
    public virtual bool IsBasicStrikeOrDefend { get; }
    public virtual OrbEvokeType OrbEvokeType => OrbEvokeType.None;
    protected virtual bool IsPlayable => true;
    protected virtual bool ShouldGlowGoldInternal => false;
    protected virtual bool ShouldGlowRedInternal => false;

    // 图像
    public virtual string PortraitPath { get; }
    public virtual string BetaPortraitPath { get; }
    public virtual IEnumerable<string> AllPortraitPaths { get; }
    protected virtual IEnumerable<string> ExtraRunAssetPaths => Array.Empty<string>();

    // 本地化
    public virtual IEnumerable<DynamicVar> CanonicalVars { get; }
    protected virtual void AddExtraArgsToDescription(LocString description)

    // 生命周期 Hook（卡牌核心方法）
    public virtual void AfterCreated()
    protected virtual void AfterDeserialized()
    public virtual void AfterTransformedFrom()
    public virtual void AfterTransformedTo()
    protected virtual void OnUpgrade()
    protected virtual void AfterDowngraded()
    protected virtual PileType GetResultPileType()

    // *** 关键：卡牌出牌效果方法 ***
    // 由 CardCmd.AutoPlay/Play 内部调用，不要直接调用
    protected virtual Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)

    // 回合结束留手效果（需要 HasTurnEndInHandEffect => true）
    public virtual Task OnTurnEndInHand(PlayerChoiceContext choiceContext)

    // 出牌 VFX
    public virtual Task OnEnqueuePlayVfx(Creature? target)
}
```

**实际继承路径（使用 BaseLib 时）：**
```
YourCard → CustomCardModel (BaseLib) → CardModel → AbstractModel
```

BaseLib 的 `CustomCardModel` 提供了 `[Pool]` 属性注入和便捷辅助方法，直接继承 `CardModel` 也可以工作但需手动实现更多内容。

---

## PowerModel（Power/Buff 系统）

```csharp
namespace MegaCrit.Sts2.Core.Models;

// 继承自 AbstractModel（获得所有战斗 hook）
public abstract class PowerModel : AbstractModel
{
    public const string locTable = "powers";

    // 必须实现
    public abstract PowerType Type { get; }           // Buff / Debuff / None
    public abstract PowerStackType StackType { get; } // Counter / Single / None

    // 重要继承：
    public override bool ShouldReceiveCombatHooks => true;

    // 数量
    public int Amount { get; set; }
    public int AmountOnTurnStart { get; set; }
    public virtual int DisplayAmount => Amount;
    public virtual Color AmountLabelColor { get; }
    public virtual bool AllowNegative => false;

    // 所有者
    public Creature Owner { get; }      // private set，通过 ApplyInternal 设置
    public Creature? Applier { get; set; }
    public Creature? Target { get; set; }
    public CombatState CombatState => Owner.CombatState;

    // 可见性
    protected virtual bool IsVisibleInternal => true;
    public bool IsVisible { get; }
    public virtual bool ShouldPlayVfx { get; }

    // 多人游戏
    public virtual bool ShouldScaleInMultiplayer => false;
    public virtual bool OwnerIsSecondaryEnemy => false;
    public virtual bool IsInstanced => false;

    // 图标
    public string PackedIconPath { get; }
    public string ResolvedBigIconPath { get; }
    public Texture2D Icon { get; }
    public Texture2D BigIcon { get; }

    // 本地化
    public virtual LocString Title => new LocString("powers", Id.Entry + ".title");
    public virtual LocString Description => new LocString("powers", Id.Entry + ".description");
    protected virtual string SmartDescriptionLocKey { get; }
    protected virtual string RemoteDescriptionLocKey { get; }

    // 动态变量
    public DynamicVarSet DynamicVars { get; }
    protected virtual IEnumerable<DynamicVar> CanonicalVars => Array.Empty<DynamicVar>();
    protected virtual object? InitInternalData()
    protected T GetInternalData<T>()

    // 生命周期 Hook（Power 专属）
    public virtual Task BeforeApplied(Creature target, decimal amount, Creature? applier, CardModel? cardSource)
    public virtual Task AfterApplied(Creature? applier, CardModel? cardSource)
    public virtual Task AfterRemoved(Creature oldOwner)
    public virtual bool ShouldPowerBeRemovedAfterOwnerDeath()
    public virtual bool ShouldOwnerDeathTriggerFatal()

    // 内部操作（由 PowerCmd 调用，不要直接使用）
    public void SetAmount(int amount, bool silent = false)
    public PowerModel ToMutable(int initialAmount = 0)
    public void ApplyInternal(Creature owner, decimal amount, bool silent = false)
    public void RemoveInternal()
    public bool ShouldRemoveDueToAmount()
    public PowerType GetTypeForAmount(decimal customAmount)

    // 持续时间相关
    public bool SkipNextDurationTick { get; set; }

    // 事件
    public event Action? PulsingStarted;
    public event Action? PulsingStopped;
    public event Action<PowerModel>? Flashed;
    public event Action? DisplayAmountChanged;
    public event Action? Removed;
}
```

**如何实现一个 Power（从反编译推断的最小实现）：**

```csharp
// 最小实现示例（Buff，叠加计数型）
[Pool]  // 需要 BaseLib 或类似属性
public class MyPower : PowerModel   // 或 CustomCardModel 所在库里的等价基类
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    // 通过 override AbstractModel 的 hook 实现效果，例如：
    public override async Task AfterCardPlayed(PlayerChoiceContext ctx, CardPlay cardPlay)
    {
        // 效果逻辑
        await base.AfterCardPlayed(ctx, cardPlay);
    }
}
```

**图标路径约定：** `atlases/power_atlas.sprites/<id_lowercase>.tres`

**应用 Power 的方式（通过命令系统）：**
- 通过 `PowerCmd` 或 `CreatureCmd` 中的静态方法（需进一步确认具体方法名）
- `PowerModel.ApplyInternal(Creature owner, decimal amount)` 是底层实现

---

## Player

```csharp
namespace MegaCrit.Sts2.Core.Entities.Players;

public class Player
{
    // 关联实体
    public CharacterModel Character { get; }
    public Creature Creature { get; }
    public ulong NetId { get; }

    // 状态
    public IRunState RunState { get; set; }
    public PlayerCombatState? PlayerCombatState { get; }
    public ExtraPlayerFields ExtraFields { get; }
    public bool IsActiveForHooks { get; }
    public int MaxAscensionWhenRunStarted { get; }

    // 资源
    public int Gold { get; set; }
    public int MaxEnergy { get; set; }

    // 牌组 / 牌堆
    public CardPile Deck { get; }           // PileType.Deck
    public IEnumerable<CardPile> Piles { get; }

    // 遗物 / 药水
    public IReadOnlyList<RelicModel> Relics { get; }
    public IReadOnlyList<PotionModel?> PotionSlots { get; }
    public IEnumerable<PotionModel> Potions { get; }
    public int MaxPotionCount { get; }
    public bool HasOpenPotionSlots { get; }
    public bool CanRemovePotions { get; set; }

    // 宠物
    public Creature? Osty { get; }
    public bool IsOstyAlive { get; }
    public bool HasEventPet()

    // 随机/概率
    public PlayerRngSet PlayerRng { get; }
    public PlayerOddsSet PlayerOdds { get; }
    public RelicGrabBag RelicGrabBag { get; }
    public UnlockState UnlockState { get; }

    // 探索记录
    public List<ModelId> DiscoveredCards { get; set; }
    public List<ModelId> DiscoveredRelics { get; set; }
    public List<ModelId> DiscoveredPotions { get; set; }
    public List<ModelId> DiscoveredEnemies { get; set; }
    public List<string> DiscoveredEpochs { get; set; }
    public int BaseOrbSlotCount { get; set; }

    // 事件
    public event Action<RelicModel>? RelicObtained;
    public event Action<RelicModel>? RelicRemoved;
    public event Action<int>? MaxPotionCountChanged;
    public event Action<PotionModel>? PotionProcured;
    public event Action<PotionModel>? PotionDiscarded;
    public event Action<PotionModel>? UsedPotionRemoved;
    public event Action? AddPotionFailed;
    public event Action? GoldChanged;
}
```

---

## Creature

```csharp
namespace MegaCrit.Sts2.Core.Entities.Creatures;

public class Creature
{
    // 身份
    public MonsterModel? Monster { get; }
    public Player? Player { get; }
    public ModelId ModelId { get; }
    public uint? CombatId { get; set; }
    public string Name { get; }
    public string? SlotName { get; set; }

    // HP / 护盾
    public int Block { get; }
    public int CurrentHp { get; }
    public int MaxHp { get; }
    public bool ShowsInfiniteHp { get; set; }
    public bool IsAlive => CurrentHp > 0;
    public bool IsDead => !IsAlive;

    // 阵营
    public CombatSide Side { get; }
    public bool IsMonster => Monster != null;
    public bool IsPlayer => Player != null;
    public bool IsEnemy => Side == CombatSide.Enemy;
    public bool IsPrimaryEnemy { get; }
    public bool IsSecondaryEnemy { get; }
    public bool IsHittable { get; }
    public bool CanReceivePowers { get; }
    public bool IsStunned { get; }

    // 宠物
    public Player? PetOwner { get; }
    public bool IsPet => PetOwner != null;
    public IReadOnlyList<Creature> Pets { get; }

    // 战斗状态
    public CombatState? CombatState { get; set; }

    // Power 查询
    public IReadOnlyList<PowerModel> Powers { get; }
    public bool HasPower<T>() where T : PowerModel
    public bool HasPower(ModelId id)
    public T? GetPower<T>() where T : PowerModel
    public PowerModel? GetPower(ModelId id)
    public IEnumerable<T> GetPowerInstances<T>() where T : PowerModel
    public PowerModel? GetPowerById(ModelId id)

    // 内部操作（由命令系统调用）
    public DamageResult LoseHpInternal(decimal amount, ValueProp props)
    public decimal DamageBlockInternal(decimal amount, ValueProp props)
    public void GainBlockInternal(decimal amount)
    public void LoseBlockInternal(decimal amount)
    public void HealInternal(decimal amount)
    public void SetCurrentHpInternal(decimal amount)
    public void SetMaxHpInternal(decimal amount)
    public void Reset()

    // 事件
    public event Action<int, int>? BlockChanged;
    public event Action<int, int>? CurrentHpChanged;
    public event Action<int, int>? MaxHpChanged;
    public event Action<PowerModel>? PowerApplied;
    public event Action<PowerModel, int, bool>? PowerIncreased;
    public event Action<PowerModel, bool>? PowerDecreased;
    public event Action<PowerModel>? PowerRemoved;
    public event Action<Creature>? Died;
    public event Action<Creature>? Revived;
}
```

---

## DamageResult

```csharp
namespace MegaCrit.Sts2.Core.Entities.Creatures;

public class DamageResult
{
    public Creature Receiver { get; }
    public ValueProp Props { get; }
    public int BlockedDamage { get; set; }
    public int UnblockedDamage { get; init; }
    public int OverkillDamage { get; init; }
    public int TotalDamage => BlockedDamage + UnblockedDamage;
    public bool WasBlockBroken { get; set; }
    public bool WasFullyBlocked { get; set; }
    public bool WasTargetKilled { get; init; }

    public DamageResult(Creature receiver, ValueProp props)
}
```

---

## SharedRelicPool

```csharp
namespace MegaCrit.Sts2.Core.Models.RelicPools;

public sealed class SharedRelicPool : RelicPoolModel
{
    public override string EnergyColorName => "colorless";

    // 内部实现：返回 118 个共享遗物（不含各角色专属遗物）
    protected override IEnumerable<RelicModel> GenerateAllRelics()

    // 解锁过滤（根据 Epoch 解锁状态）
    public override IEnumerable<RelicModel> GetUnlockedRelics(UnlockState unlockState)
}
```

---

## ModelDb（静态注册表）

> **⚠️ 严禁直接 new Model！**
> STS2 的所有 Model（CardModel、RelicModel、MonsterModel 等）在程序启动时由引擎注册为"canonical 单例"。
> 如果用 `new XxxModel()` 直接构造，会抛出 `DuplicateModelException` 导致进游戏黑屏，
> 且报错信息不会明确指出是"用了 new"，极难排查。
>
> **正确做法**：
> - 读取 canonical：`ModelDb.Relic<T>()` / `ModelDb.Card<T>()` / `ModelDb.Monster<T>()`
> - 创建 run 内可变副本：在 canonical 上调用 `.ToMutable()`
> - 示例：`player.AddRelicInternal(ModelDb.Relic<MyRelic>().ToMutable());`
> - 错误示例：`player.AddRelicInternal(new MyRelic());`  // ❌ DuplicateModelException

```csharp
namespace MegaCrit.Sts2.Core.Models;

public static class ModelDb
{
    // 查询集合
    public static IEnumerable<CardModel> AllCards { get; }
    public static IEnumerable<CardPoolModel> AllCardPools { get; }
    public static IEnumerable<CardPoolModel> AllSharedCardPools { get; }
    public static IEnumerable<CardPoolModel> AllCharacterCardPools { get; }
    public static IEnumerable<CharacterModel> AllCharacters { get; }  // Ironclad, Silent, Regent, Necrobinder, Defect
    public static IEnumerable<EventModel> AllEvents { get; }
    public static IEnumerable<EventModel> AllSharedEvents { get; }
    public static IEnumerable<MonsterModel> Monsters { get; }
    public static IEnumerable<EncounterModel> AllEncounters { get; }
    public static IEnumerable<PotionModel> AllPotions { get; }
    public static IEnumerable<PotionPoolModel> AllPotionPools { get; }
    public static IEnumerable<PowerModel> AllPowers { get; }
    public static IEnumerable<RelicModel> AllRelics { get; }
    public static IEnumerable<RelicPoolModel> AllRelicPools { get; }
    public static IEnumerable<RelicPoolModel> CharacterRelicPools { get; }
    public static IEnumerable<OrbModel> Orbs { get; }
    public static IEnumerable<ActModel> Acts { get; }
    public static IReadOnlyList<AchievementModel> Achievements { get; }
    public static IReadOnlyList<ModifierModel> GoodModifiers { get; }
    public static IReadOnlyList<ModifierModel> BadModifiers { get; }

    // 按类型获取实例（canonical，不可变）
    public static T Card<T>() where T : CardModel
    public static T Character<T>() where T : CharacterModel
    public static T Power<T>() where T : PowerModel
    public static T Relic<T>() where T : RelicModel

    // 池类型访问（新角色/自定义池必须用这些）
    public static T CardPool<T>() where T : CardPoolModel
    public static T RelicPool<T>() where T : RelicPoolModel
    public static T PotionPool<T>() where T : PotionPoolModel

    // 按 ID 获取
    public static T GetById<T>(ModelId id) where T : AbstractModel
    public static T? GetByIdOrNull<T>(ModelId id) where T : AbstractModel

    // 其他
    public static ModelId GetId<T>() where T : AbstractModel
    public static ModelId GetId(Type type)
    public static Type GetCategoryType(Type type)
    public static string GetCategory(Type type)
    public static string GetEntry(Type type)
    public static void Init()
    public static void Inject([DynamicallyAccessedMembers(...)] Type type)
    public static void Remove(Type type)
    public static void InitIds()
    public static void Preload()
}
```

---

## CardCmd（静态命令类）

```csharp
namespace MegaCrit.Sts2.Core.Commands;

public static class CardCmd
{
    // 出牌（主要入口）
    public static async Task AutoPlay(PlayerChoiceContext choiceContext, CardModel card, Creature? target,
        AutoPlayType type = AutoPlayType.Default, bool skipXCapture = false, bool skipCardPileVisuals = false)

    // 弃牌
    public static async Task Discard(PlayerChoiceContext choiceContext, CardModel card)
    public static async Task Discard(PlayerChoiceContext choiceContext, IEnumerable<CardModel> cards)
    public static async Task DiscardAndDraw(PlayerChoiceContext choiceContext, IEnumerable<CardModel> cardsToDiscard, int cardsToDraw)

    // 升降级
    public static void Upgrade(CardModel card, CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)
    public static void Upgrade(IEnumerable<CardModel> cards, CardPreviewStyle style)
    public static void Downgrade(CardModel card)

    // 消耗
    public static async Task Exhaust(PlayerChoiceContext choiceContext, CardModel card,
        bool causedByEthereal = false, bool skipVisuals = false)

    // 变形
    public static async Task<CardPileAddResult> TransformToRandom(CardModel original, Rng rng,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)
    public static async Task<CardPileAddResult?> TransformTo<T>(CardModel original,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout) where T : CardModel
    public static async Task<CardPileAddResult?> Transform(CardModel original, CardModel replacement,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)
    public static async Task<IEnumerable<CardPileAddResult>> Transform(IEnumerable<CardTransformation> transformations,
        Rng? rng, CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)

    // 附魔 / 诅咒
    public static T? Enchant<T>(CardModel card, decimal amount) where T : EnchantmentModel
    public static EnchantmentModel? Enchant(EnchantmentModel enchantment, CardModel card, decimal amount)
    public static void ClearEnchantment(CardModel card)
    public static async Task<IEnumerable<T>> AfflictAndPreview<T>(IEnumerable<CardModel> cards, decimal amount,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout) where T : AfflictionModel
    public static async Task<T?> Afflict<T>(CardModel card, decimal amount) where T : AfflictionModel
    public static Task<AfflictionModel?> Afflict(AfflictionModel affliction, CardModel card, decimal amount)
    public static void ClearAffliction(CardModel card)

    // 关键词
    public static void ApplyKeyword(CardModel card, params CardKeyword[] keywords)
    public static void RemoveKeyword(CardModel card, params CardKeyword[] keywords)
    public static void ApplySingleTurnSly(CardModel card)

    // 预览 UI
    public static TaskCompletionSource? Preview(CardModel card, float time = 1.2f,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)
    public static void Preview(IReadOnlyList<CardModel> cards, float time = 1.2f,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)
    public static void PreviewCardPileAdd(CardPileAddResult result, float time = 1.2f,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)
    public static void PreviewCardPileAdd(IReadOnlyList<CardPileAddResult> results, float time = 1.2f,
        CardPreviewStyle style = CardPreviewStyle.HorizontalLayout)
}
```

---

## CardSelectCmd（战斗内外均可用）

> **关键发现**：`FromSimpleGridForRewards` 和 `FromSimpleGrid` 头部只检查 `CombatManager.Instance.IsEnding`（战斗正在结束时提前返回空），并不要求战斗进行中。BrainLeech 事件（纯战斗外场景）直接调用此方法，证明其在 Neow / 事件中完全可用。

```csharp
namespace MegaCrit.Sts2.Core.Commands;

public static class CardSelectCmd
{
    // ── 战斗外 / 事件内选牌（BrainLeech 证明可用）──────────────────────────

    // 展示格子 UI，从 CardCreationResult 列表中选牌（可多选）
    // 用于事件、奖励等场景。参数：
    //   context  — new BlockingPlayerChoiceContext()（事件中使用）
    //   cards    — List<CardCreationResult>，可包含任意数量的牌
    //   player   — 当前玩家
    //   prefs    — CardSelectorPrefs（控制最少/最多选多少张）
    public static async Task<IEnumerable<CardModel>> FromSimpleGridForRewards(
        PlayerChoiceContext context,
        List<CardCreationResult> cards,
        Player player,
        CardSelectorPrefs prefs)

    // 同上，但直接接受 IReadOnlyList<CardModel>（无 CardCreationResult 包装）
    public static async Task<IEnumerable<CardModel>> FromSimpleGrid(
        PlayerChoiceContext context,
        IReadOnlyList<CardModel> cardsIn,
        Player player,
        CardSelectorPrefs prefs)

    // ── 战斗内选牌（仅在 CombatManager.Instance 存在时调用）────────────────

    // 从手牌选牌
    public static async Task<IEnumerable<CardModel>> FromHand(
        PlayerChoiceContext context, Player player, CardSelectorPrefs prefs)

    // 从牌组选牌（用于升级、移除等）
    public static async Task<IEnumerable<CardModel>> FromDeckForUpgrade(
        Player player, CardSelectorPrefs prefs)
    public static async Task<IEnumerable<CardModel>> FromDeckForRemoval(
        Player player, CardSelectorPrefs prefs,
        Func<CardModel, bool>? filter = null)
    public static async Task<IEnumerable<CardModel>> FromDeckForEnchantment(
        List<CardModel> cards, EnchantmentModel enchantment,
        decimal amount, CardSelectorPrefs prefs)

    // 奖励选牌界面（3 张，上方弧形展示，上限 3 张否则抛出 ArgumentException）
    public static async Task<CardModel?> FromChooseACardScreen(
        PlayerChoiceContext context, IReadOnlyList<CardModel> cards, Player player)
}
```

### CardCreationResult（选牌 UI 的卡牌包装器）

```csharp
namespace MegaCrit.Sts2.Core.Entities.Cards;

public class CardCreationResult
{
    public readonly CardModel originalCard;
    public CardModel Card => _modifiedCard ?? originalCard;  // 显示的牌
    public bool HasBeenModified { get; }

    // 直接包装任意 CardModel 即可（无其他依赖）
    public CardCreationResult(CardModel originalCard)
    public void ModifyCard(CardModel card, RelicModel modifyingRelic)
}
```

### CardSelectorPrefs（选牌数量控制）

```csharp
namespace MegaCrit.Sts2.Core.CardSelection;

public struct CardSelectorPrefs
{
    public int MinSelect { get; }
    public int MaxSelect { get; }
    // RequireManualConfirmation = MinSelect >= 0 && MinSelect != MaxSelect
    // → 若 true，UI 显示 Confirm 按钮；否则选够 MaxSelect 张自动确认
    public bool RequireManualConfirmation { get; init; }
    public bool Cancelable { get; init; }

    // (prompt, selectCount)           → MinSelect = MaxSelect = selectCount
    public CardSelectorPrefs(LocString prompt, int selectCount)
    // (prompt, minCount, maxCount)    → 支持区间选择，自动设置 RequireManualConfirmation
    public CardSelectorPrefs(LocString prompt, int minCount, int maxCount)

    // 内置 Prompt 常量（可复用）
    public static LocString UpgradeSelectionPrompt
    public static LocString RemoveSelectionPrompt
    public static LocString ExhaustSelectionPrompt
    // ...
}
```

### 非战斗选牌完整模式（BrainLeech / SFTestKit 验证）

```csharp
using MegaCrit.Sts2.Core.CardSelection;           // CardSelectorPrefs
using MegaCrit.Sts2.Core.Commands;                // CardSelectCmd, CardCmd, CardPileCmd
using MegaCrit.Sts2.Core.Entities.Cards;          // CardCreationResult, PileType
using MegaCrit.Sts2.Core.GameActions.Multiplayer; // BlockingPlayerChoiceContext

// 1. 创建所有卡的可变实例（含所有 mod 加入的卡）
var allCards = ModelDb.AllCards
    .Select(m => new CardCreationResult(player.RunState.CreateCard(m, player)))
    .ToList();

// 2. 配置选择参数（minSelect=0, maxSelect=N → 显示 Confirm 按钮）
var prefs = new CardSelectorPrefs(
    CardSelectorPrefs.UpgradeSelectionPrompt,  // 或自定义 LocString
    minCount: 0,
    maxCount: allCards.Count
);

// 3. 打开格子选牌 UI（在 Neow/事件的 async Task 方法里调用）
var selected = (await CardSelectCmd.FromSimpleGridForRewards(
    new BlockingPlayerChoiceContext(), allCards, player, prefs)).ToList();

// 4. 将选中的牌加入牌组
foreach (var card in selected)
    CardCmd.PreviewCardPileAdd(await CardPileCmd.Add(card, PileType.Deck));
```

---

## RelicSelectCmd（战斗外完整遗物列表，已验证）

```csharp
namespace MegaCrit.Sts2.Core.Commands;

public static class RelicSelectCmd
{
    // 弹出可滚动遗物列表（S00_DebugPicker 和 SFTestKit 均验证可在 Neow 事件中调用）
    // relics 可传入所有遗物的完整列表，UI 自动支持滚动
    public static async Task<RelicModel?> FromChooseARelicScreen(
        Player player,
        IReadOnlyList<RelicModel> relics)
}
```

**标准用法（在 Neow EventOption 回调里）：**
```csharp
var allRelics = ModelDb.AllRelics
    .Where(r => r.Rarity is not RelicRarity.Starter and not RelicRarity.None)
    .Select(r => r.ToMutable())
    .ToList();

var picked = await RelicSelectCmd.FromChooseARelicScreen(player, allRelics);
if (picked != null)
    player.AddRelicInternal(picked);
```

---

## RunState.CreateCard（从模板创建可变卡牌实例）

```csharp
// RunState（通过 player.RunState 访问）
public CardModel CreateCard(CardModel canonicalCard, Player owner)
// 等价于：
//   CardModel cardModel = canonicalCard.ToMutable();
//   // + 设置 Owner、注册到 RunState 等初始化操作

// 泛型版（已知类型时）
public T CreateCard<T>(Player owner) where T : CardModel
//  → 等价于 CreateCard(ModelDb.Card<T>(), owner)
```

**用于事件/Neow 中批量创建可用卡实例：**
```csharp
// 从 canonical 模板创建 mutable 实例（不是 new CardModel()！）
CardModel mutable = player.RunState.CreateCard(ModelDb.Card<StrikeIronclad>(), player);

// 批量创建所有卡（含 mod 卡）
var cards = ModelDb.AllCards
    .Select(m => player.RunState.CreateCard(m, player))
    .ToList();
```

---

## BlockingPlayerChoiceContext（事件用无操作 Context）

```csharp
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer;

// 在事件/Neow 中调用 CardSelectCmd 时使用
// 两个方法都是 no-op（直接返回 Task.CompletedTask）
public class BlockingPlayerChoiceContext : PlayerChoiceContext
{
    public override Task SignalPlayerChoiceBegun(PlayerChoiceOptions options) => Task.CompletedTask;
    public override Task SignalPlayerChoiceEnded() => Task.CompletedTask;
}
```

---

## PlayerChoiceContext

```csharp
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer;

public abstract class PlayerChoiceContext
{
    public AbstractModel? LastInvolvedModel { get; }

    public void PushModel(AbstractModel model)
    public void PopModel(AbstractModel model)

    // 多人游戏选择信号
    public abstract Task SignalPlayerChoiceBegun(PlayerChoiceOptions options)
    public abstract Task SignalPlayerChoiceEnded()
}
```

---

## 枚举

### PileType
```csharp
namespace MegaCrit.Sts2.Core.Entities.Cards;
public enum PileType { None, Draw, Hand, Discard, Exhaust, Play, Deck }
```

### CardType
```csharp
namespace MegaCrit.Sts2.Core.Entities.Cards;
public enum CardType { None, Attack, Skill, Power, Status, Curse, Quest }
```

### CardRarity
```csharp
namespace MegaCrit.Sts2.Core.Entities.Cards;
public enum CardRarity { None, Basic, Common, Uncommon, Rare, Ancient, Event, Token, Status, Curse, Quest }
```

### TargetType
```csharp
namespace MegaCrit.Sts2.Core.Entities.Cards;
public enum TargetType { None, Self, AnyEnemy, AllEnemies, RandomEnemy, AnyPlayer, AnyAlly, AllAllies, TargetedNoCreature, Osty }
```

### RelicRarity
```csharp
namespace MegaCrit.Sts2.Core.Entities.Relics;
public enum RelicRarity { None, Starter, Common, Uncommon, Rare, Shop, Event, Ancient }
```

### PowerType
```csharp
namespace MegaCrit.Sts2.Core.Entities.Powers;
public enum PowerType { None, Buff, Debuff }
```

### PowerStackType
```csharp
namespace MegaCrit.Sts2.Core.Entities.Powers;
public enum PowerStackType { None, Counter, Single }
```

---

## 角色列表

`ModelDb.AllCharacters` 固定包含 5 个角色（按顺序）：
1. `Ironclad`
2. `Silent`
3. `Regent`
4. `Necrobinder`
5. `Defect`

---

---

## PotionModel（药水系统）

> `CustomPotionModel` 在 BaseLib，不在 decompiled_tmp。源码：`https://github.com/Alchyr/BaseLib-StS2/blob/master/Abstracts/CustomPotionModel.cs`

```csharp
// 最小实现（BaseLib）
[Pool(typeof(SharedPotionPool))]
public class MyPotion : CustomPotionModel
{
    public override PotionRarity Rarity    => PotionRarity.Common;
    public override PotionUsage  Usage     => PotionUsage.CombatOnly;   // 或 AnyTime
    public override TargetType   TargetType => TargetType.Self;

    // 条件使用（属性，不是方法）
    public override bool PassesCustomUsabilityCheck => Owner.Creature.CurrentHp > 8;

    // 效果方法（是 OnUse，不是 Use 或 OnApply）
    protected override async Task OnUse(PlayerChoiceContext choiceContext, Creature? target)
    {
        await PowerCmd.Apply<StrengthPower>(Owner.Creature, 3m, Owner.Creature, null);
        await CreatureCmd.Damage(choiceContext, Owner.Creature, 8m, ValueProp.Unblockable, null, null);
    }
}
```

**本地化 key 前缀规则（BaseLib TypePrefix）：**
- BaseLib 从根命名空间推导 key 前缀：`{NAMESPACE_ROOT}-{CLASS_NAME}` (UPPER_SNAKE_CASE)
- 例：namespace `S07_BerserkerBrew.Potions`，class `BerserkerBrew` → key `S07_BERSERKERBREW-BERSERKER_BREW`
- 药水 JSON 文件：`localization/eng/potions.json`（表名 `"potions"`）

---

## CharacterModel（新角色系统）

新角色需要以下 5 个部分：

```
Characters/Arcanist.cs          ← PlaceholderCharacterModel 子类
CardPools/ArcanistCardPool.cs   ← CustomCardPoolModel
RelicPools/ArcanistRelicPool.cs ← CustomRelicPoolModel
PotionPools/ArcanistPotionPool.cs ← CustomPotionPoolModel
localization/eng/characters.json  ← 必须，独立于 cards.json/relics.json
```

```csharp
// PlaceholderCharacterModel — 用 Ironclad 占位图，不需要自己的美术资源
public sealed class Arcanist : PlaceholderCharacterModel
{
    public override string PlaceholderID => "ironclad";   // 复用 ironclad 所有视觉资源
    public override Color NameColor => new Color("8B5CF6");
    public override CharacterGender Gender => CharacterGender.Neutral;
    public override int StartingHp => 60;

    public override CardPoolModel   CardPool   => ModelDb.CardPool<ArcanistCardPool>();
    public override RelicPoolModel  RelicPool  => ModelDb.RelicPool<ArcanistRelicPool>();
    public override PotionPoolModel PotionPool => ModelDb.PotionPool<ArcanistPotionPool>();

    public override IEnumerable<CardModel> StartingDeck =>
        [ModelDb.Card<ArcaneStrike>(), ModelDb.Card<ArcaneStrike>(), ...];

    public override IReadOnlyList<RelicModel> StartingRelics =>
        [ModelDb.Relic<ArcaneOrb>()];

    public override List<string> GetArchitectAttackVfx()
        => ["vfx/vfx_attack_slash", "vfx/vfx_attack_blunt", "vfx/vfx_heavy_blunt"];
}

// Pool 最小实现
public class ArcanistCardPool : CustomCardPoolModel { }
public class ArcanistRelicPool : CustomRelicPoolModel { }
public class ArcanistPotionPool : CustomPotionPoolModel
{
    public override PotionPoolModel? ParentPool => ModelDb.PotionPool<SharedPotionPool>();
}
```

**characters.json 格式（必须创建，不能省略）：**
```json
{
  "S09_ARCANIST-ARCANIST.name": "Arcanist",
  "S09_ARCANIST-ARCANIST.description": "A wielder of arcane energies."
}
```

---

## 注意事项

1. **Hook 触发条件**：`ShouldReceiveCombatHooks` 必须返回 `true`，hook 才会被调用。RelicModel 和 PowerModel 默认为 `true`；CardModel 的默认实现是 `Pile?.IsCombatPile ?? false`（即只在战斗牌堆中才激活）。

2. **`OnPlay` vs 战斗 hook 的区别**：
   - `OnPlay(PlayerChoiceContext, CardPlay)` 是卡牌被打出时的专属效果（相当于 STS1 的 `use()`）
   - `AfterCardPlayed/BeforeCardPlayed` 等是所有 model 都能监听的全局事件

3. **Power 的应用方式**：不直接 `new` 并调用 `ApplyInternal`，应通过 `PowerCmd`（或 `CreatureCmd`）静态方法——具体方法名需查看 `MegaCrit.Sts2.Core.Commands/PowerCmd.cs`（或 BaseLib 中的等价物）。

4. **异步设计**：几乎所有游戏效果方法都返回 `Task`，配合 `await` 使用以保证时序正确。

