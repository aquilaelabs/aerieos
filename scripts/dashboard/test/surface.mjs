#!/usr/bin/env node
// The page's top-level surface, written down, so that changing it is a
// deliberate line in a diff rather than something that happens.
//
// index.html is one file of vanilla JS with no build step and no module
// boundary: the stated design, and the reason `aerie dashboard test` can drive
// its internals directly. What it lacks is any way to notice code landing in
// the WRONG scope. That is not hypothetical: a feature written this week was
// declared three braces deep inside makeNotebook, a per-notebook factory, so
// the projects card calling it got "openTrash is not defined", and an earlier
// one read a const before its initializer across ten thousand lines (bug #27).
// Both were eventually caught by a console error in a suite that happened to
// exercise the path. This catches them by name, in one place, immediately.
//
// It runs in BOTH directions on purpose.
//
//   MISSING means a name that used to be top-level is not any more: deleted,
//   renamed, or fallen into a nested scope. The last of those is the bug.
//
//   NEW means a global appeared. That is not an error, but it should be a
//   decision: this file already carries 84 mutable top-level bindings, and
//   every one of them is a thing two pieces of code can disagree about. Adding
//   a line here is the cost of adding one, and it is meant to be felt.
//
// A `function` or `var` at the top level of a classic script becomes a
// property of window; `let` and `const` go into the global LEXICAL scope,
// reachable by bare name and invisible to getOwnPropertyNames. So the
// inventory below covers the function/var half (192 names), and the named
// check underneath asks by bare name instead, which is how the markup and the
// suite actually reach them. Worth knowing rather than discovering: a feature
// written entirely as `const fn = () => …` is not covered by the inventory.
import { launch, newPage, ok, done, ready, URL } from './lib.mjs';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// Sorted, and one entry per name. Regenerate by failing the test and reading
// what it prints. Do not hand-edit it into agreement without looking at why
// it moved.
const SURFACE = [ 'adoptLayout', 'adoptMode', 'adoptMotion', 'applyMotion', 'adoptTheme', 'applyMode', 'applyNow', 'askProjectGroup', 'renameProjectGroup', 'pickProjectColor', 'applyTheme',
  'sectRemember', 'sectRecall', 'isToolKind', 'groupOf', 'railAllows', 'railGroups', 'railOn', 'railGo', 'shellPush', 'routeOf', 'openRoute', 'shellSync', 'shellBoot', 'shown',
  'drawRail', 'railMoreShow', 'shellBar', 'wireShellBar', 'jumpItems', 'drawJump', 'jumpMove', 'jumpGo', 'wireJump', 'revsDelay',
  'argForSession', 'agentsLive', 'setupDiskPlan', 'setupPlanned', 'setupDiskSplit', 'setupDisksLoad', 'setupDisksSig', 'setupDisksCard', 'wireSetupDisks', 'pnoteBand', 'pnoteOnShow', 'openEntry', 'loadEntry', 'entryRow', 'entryLabel', 'renderEntryInto', 'libIcon', 'openThing', 'thingRow', 'thingLabel', 'renderThingInto', 'instAboutLines', 'instConfigLines', 'instConfigurable', 'shellCame', 'kindOfRoute', 'routeLabel', 'backHead', 'shellBack', 'dmConfigureBtn', 'agentsAdopt', 'libGroup', 'libTierWord', 'agExtras', 'routerModels', 'routerTooSmall', 'routerSays', 'agentPicker', 'agentAsker', 'byWho', 'rnFillAgents', 'launchAgent', 'agentEnd', 'dropAgentTab', 'myLiveSession', 'agentLogins', 'sendAgent', 'openSentTo', 'agentById', 'agentOfSession', 'agentSessionWords', 'agentOfArg', 'agentsWord', 'agentArg', 'mySlots', 'freeSlot', 'loadRmConvs', 'pickSend', 'armModal', 'arriveBox', 'askPurge', 'askReset', 'nginxHostPick', 'nginxHostLines', 'claudeRestart', 'restartNow', 'unenrollWhat', 'resetBusy', 'resetFollow', 'resetGone', 'cSeg', 'cSlide',
  'askVerb', 'cSubmit', 'cUnderPicked', 'daemonHost',
  'dmGo', 'cNameSay', 'cInstanceSay', 'cFollowRow', 'storageForget', 'phGone', 'nginxLanded',
  'dmAhead', 'ndAhead', 'ndQueuedSay', 'storageJobSaid', 'machineSaid', 'nginxBuilding',
  'closeNewProject', 'createProject',
  'closeRename', 'closeSendToDocker', 'bootPage', 'bootRail', 'skSplit', 'dockDragStart', 'dockDragMove', 'dockDragEnd', 'dockHeld', 'dockNoScroll', 'dockPlaceTab', 'nodeCharted',
  'currentMode', 'currentTheme', 'deleteProject', 'dmAction', 'dnShow',
  'dmState', 'dmWireRows', 'dmViewSeg', 'dmViewWire', 'dmCheck', 'dnNodeSay', 'dnSubmit', 'docSurface', 'docSection', 'skel', 'skv', 'skRows', 'skTpl', 'skOpen', 'skTable', 'skProjectCard', 'projectsShown', 'slideCards', 'moveConfirm', 'pjFadeArm', 'faceFade', 'showNewCard', 'barSaid', 'dmBar', 'dmTiles', 'dmBootLoad', 'dmStatus', 'dmImagesSection', 'dmOldApps', 'dmOldAppsKey', 'downloadOldCompose', 'ndBar', 'ndFacts', 'ndUpdatesFact', 'ndInUse', 'ndDialogs', 'nodeSessSettings', 'nodeSessDirty', 'setupSteps', 'wireSetup', 'homeStartHtml', 'homeStartReadsNodes', 'homeStartSteps', 'phoneCheckBtn', 'nginxBar', 'jobsSection', 'tpSeen', 'tpModalHtml', 'loadCatalog', 'tpOpenCatalog', 'tpOpen', 'tpPinOf', 'tpFromCells', 'tpCatalogLine', 'tpSource', 'helpTitles', 'jobSessionWords', 'jobsToday', 'phWhy', 'tpClose', 'tpDraw', 'tpLook', 'emuSections', 'emuAddBar', 'sectFixed', 'sectNewVisit', 'ndAgentButtons', 'ndTitle', 'homeCards', 'openHelp', 'loadHelp', 'helpRead', 'helpNames', 'helpGo', 'helpScroll', 'helpNav', 'helpArticle', 'helpResults', 'helpSearch', 'renderHelpInto', 'rolesSplit', 'askSignOut', 'pageLink', 'askInline', 'comboWire', 'navPush', 'dmImage', 'railTool', 'sectAttr', 'wireSections', 'openMenu', 'openPopup', 'menuHolds', 'cardBox', 'actMore', 'statTiles', 'statusLine', 'viewGlance', 'morphThrough', 'reflow', 'slideShow', 'showBlock', 'dmHead', 'dmLine', 'ndStatusLine', 'pageNodes', 'glanceBad', 'factGrid', 'pageHead', 'saveBar', 'saveVerbs', 'dlgFoot', 'rmIcon', 'rmHold', 'noNodeYet', 'chipBar', 'chipButtons', 'chipBand', 'idOrWords', 'rmMatch', 'versionChips', 'bugMatch', 'bugFacts', 'rmDay', 'shippedIn', 'clRefs', 'clLinks', 'dmChipGroups', 'dmOwnerSaid', 'loadDockerStats', 'dmStatStrip', 'loadDockerImages', 'dmHealth', 'dmRowWrap', 'dmPorts', 'dmOpenWhy', 'dmOpenSoon', 'dmRoutesOf', 'dmMatch', 'wireMore', 'closeMore', 'floatAt', 'floatPlace', 'floatFollow', 'cardPress', 'dmNodesKey', 'emuOnNodes', 'busy', 'pctBar', 'unbusy', 'busyOff', 'copyText', 'arriveNew', 'bellHidden', 'dockerJob', 'drawBell', 'drawMaintBand', 'attRow', 'drawBuild', 'dmJumpLoad', 'dmJumpRows', 'dmJumpTo', 'busyFor',
  'drawDoctor', 'doctorChecks', 'runDoctor', 'drawKeys', 'flPlace', 'flPlaces', 'flWhen', 'flShown', 'flDeleted',
  'byProjectName', 'byProjectGroup', 'bootView', 'optionList', 'ruleWhen', 'segPick', 'skField', 'abortBtn', 'dropBox', 'drawCard', 'drawPanes', 'drawProjects', 'renderSessionsInto', 'openSessionsTab', 'sessionProject',
  'drawTrash', 'drawUiMenu', 'dressFrame',
  'dropElsewhere', 'dropTab', 'endSession',
  'findingsRulesHtml', 'flip', 'focusTab', 'foldHeight',
  'fillNodeSelect', 'fillUnderSelect', 'gateDocker', 'dropGoneNotebooks', 'getNotebook', 'hideTab',
  'killSession', 'layoutNow', 'level', 'loadDocker',
  'loadFindings', 'loadJobs', 'jobAct', 'jobTitle', 'jobsShown', 'jobsShowSet', 'jobStatePill', 'jobWord', 'jobWhen', 'jobSince', 'jobOutputs', 'loadNodes', 'nodePortsLocalRow', 'nodeHostRootRow', 'nodeRootOffLine', 'pressing', 'pressHold', 'pressRing', 'pressPick', 'pressCount', 'pressCountDone', 'drawNow', 'writeOut', 'leaveBox', 'bellLeft', 'libListSkel', 'libSkCard', 'phFit', 'phWatch', 'runAttr', 'runShow', 'goNow', 'pjRedraw', 'queuedSaid', 'libQueuedNow', 'nbArtNow', 'nbRmDrawDone', 'nbRmDrawFold', 'nbRmDrawReopen', 'nbRmDrawSplit', 'nbRmDrawStepMv', 'tcBehind', 'signOutGo', 'signedOut', 'keepFront', 'bootFront', 'nodeAct', 'nodeState', 'nodeStatePill', 'nodeTools', 'nodeGit', 'nodeGpu', 'fmtTime', 'userTZ', 'browserTZ', 'setUserTZ', 'tzOptions', 'profileDevices', 'profileSignins', 'profileAgentsSection', 'wireProfileAgents', 'loadReach', 'profileReach', 'profileReachForm', 'wireReach', 'nodeDraft', 'mountState', 'nodeMountsTable', 'nodeMountForm', 'nodeMountsSave', 'nodePathsTable', 'wireNodePaths', 'nodeStale', 'windowGap', 'staleWhy', 'storeMoves', 'ndStoreAsk', 'nodeDrift', 'nodeConfSections', 'nodeRunnerSection', 'nodeSessionsSection', 'nodeSessFacts', 'nodeRootAsksRow', 'nodeSyncRow', 'nodeSyncSaid', 'nodeHostRow', 'nodeDoorRow', 'openUnenroll', 'nodeProjects', 'nodeSpaces', 'nodeProjectsSection', 'nodeTurnsRow', 'openClustersTab', 'loadClusters', 'renderClustersInto', 'clStatus', 'clBody', 'clAddBody', 'wireClusters', 'envWhenSaid', 'principalWords', 'envNamespaceFor', 'rnLoadDeploy', 'rnDrawDeploy', 'rnEnvAddOpen', 'rnEnvSave', 'rnDrawShips', 'rnShipDraft', 'nbKubeLoad', 'nbKubeSettings', 'nbKubeDraw', 'nbKubeEnvHtml', 'nbKubeWire', 'rnEnvRemove', 'nodeHostUpdates', 'nodeRoomGroup', 'nodeAdvancedSection', 'nodeMeters', 'meter', 'dmRouteLine', 'groupNodeOptions', 'openRelocate', 'dockerDrawForms', 'rlSay', 'closeRelocate', 'rlSubmit', 'myProjectNames', 'dmRowsHtml', 'dmRefLine', 'dmOverrideLine', 'dmGpuLine', 'rnDialPart', 'rnFillRouter', 'rnDialVal', 'rnDialChoices', 'dmClaudeSaid', 'dmOwnerLine', 'dmMoveLine', 'dmNginxLine', 'dmSetDialog', 'dmRowDirty', 'runnerAddBtn', 'storageMeasureBtn', 'storageFreeable', 'storagePhones', 'dockerPrune', 'emuPhonesSaid', 'emuPhones', 'dmServicesTable', 'dmUpFor', 'dmUptime', 'dmOpenLink', 'dmPortsSaid', 'dmSetPills', 'dmInstPills', 'dmDropDrafts', 'dmRowKeys', 'dmWireStaged', 'dmApplyStaged', 'factPills', 'dmGroupsHtml', 'dmOtherRowsHtml', 'dmTestSaid', 'dmBuilt', 'jobWhy', 'dockerTab', 'dockerNodeKeep', 'loadToolchains', 'loadWire', 'logNote', 'logSection', 'nodeAgentsHere', 'mountHead',
  'chatOpen', 'consoleBar', 'drawChat', 'loadChat', 'openChatTab', 'renderChatInto', 'drawChatList', 'drawChatThread',
  'nbArtHuman', 'nbArtLoad', 'nbArtGlance', 'nbArtBuildSection', 'nbArtDockerRows', 'nbArtPushRow', 'nbArtInstallRow', 'nbArtDevNote', 'nbArtFileRow', 'nbArtCaptures', 'nbArtBranches', 'nbArtWireList', 'nbArtPoll', 'nbArtPost', 'nbArtLoadVersion', 'nbArtDrawVersion', 'nbArtVerStages', 'nbArtVerClear', 'nbArtVerCommit', 'nbArtVerSection', 'nbArtRelOf', 'nbArtRelUrl', 'nbArtVerAddFold', 'nbArtVerPolicyPicker', 'nbArtLoadDrafts', 'nbArtVerByRole', 'nbArtWireRelease', 'nbArtWireUnbump', 'nbArtWireBump', 'nbArtVerStart', 'nbArtWireInit', 'nbArtWireAsk', 'nbArtPostVersion', 'nbArtDrawChangelog', 'nbArtWireChangelog',
  'makeNotebook', 'markUiMenu',
  'nbCoreClone', 'nbCoreDrawVms', 'nbCoreNodeChips', 'nbCorePublish', 'nbCoreBag', 'nbCoreReadingRoom', 'nbCoreOpenSheet', 'nbCoreCloseSheet', 'nbCoreWireSheet', 'nbCoreViews', 'nbCoreOpenState', 'nbCoreOpenMemory', 'nbCoreNoteBatch', 'nbCoreHeld', 'nbCoreDrawBatchNote', 'nbCoreReloadViews', 'nbCoreRereadRoadmap', 'nbCoreStage', 'nbCoreSectBar', 'nbCoreBarSays', 'nbCoreSectDirty', 'nbCoreSyncSave', 'nbCoreSaveSection', 'nbCoreRevertSection', 'nbCoreWireSections', 'nbCorePresenceState', 'nbCoreOnShow', 'nbCoreBeat', 'nbCoreDrawHere', 'nbCoreSettingsEdited', 'nbCoreUnsaved', 'nbCoreLeaving', 'nbCoreSetView', 'nbCoreLeaveView', 'nbCoreWireStrip', 'nbCoreLineTo', 'nbCoreWireBugs', 'nbCoreShowing', 'nbCoreWriting', 'nbCoreWatch', 'nbCoreWatchState', 'nbCoreWatchViews', 'nbCoreHalves', 'nbCoreWatchHalves', 'nbRevRead', 'nbPoster', 'sendOutcome', 'nbCoreLoadVms', 'nbCoreWireDocker', 'nbCoreLoadDocker', 'nbCoreDrawDocker', 'nbCoreHandle', 'nbCoreShown', 'nbCoreFind', 'nbCorePoll', 'nbCoreDestroy',
  'sessionRows', 'liveRefresh', 'bootFetch', 'bootReadsDone',
  'nbReadOnly', 'newShell', 'nextShell', 'nextStep', 'notify',
  'nudgeTerminals', 'termOwn', 'xtermReady', 'termSlot', 'termUrl', 'termMount', 'termSend', 'termType', 'termFit', 'termConnect', 'wsShut', 'termEnded', 'termDrop', 'termSweep', 'termOut', 'termShow', 'termRevive', 'termKey', 'termLog', 'openLogTab', 'termPalette', 'termPreview', 'termLookPicked', 'termLook', 'termRestyle', 'termTouch', 'termCell', 'termScroll', 'termPos', 'termSelectAt', 'termSelectDraw', 'termSelText', 'termCopy', 'termSelectEnd', 'termHotKeys', 'termHotButtons', 'termHotBar', 'termLinksFill', 'termHotFolded', 'termHotWire', 'termLinks', 'mobHotRec', 'mobMoreKeys', 'mobLinksShut', 'profileTerminal', 'profileShares', 'wireShares', 'wireTerminalLook', 'onRev', 'revUntil', 'openClaude',
  'openDevEnv', 'openDocker', 'openDockerOn', 'openEditContainer', 'openEditInstance', 'cSaveInstance', 'openLinkProject',
  'openNewContainer', 'loadNasApps', 'cAppFieldHtml', 'cAppDraw', 'cAppNodePicked', 'cAppNameTyped', 'cAppFollow', 'cAppFreeName', 'cAppFreePort', 'cAppNetSay', 'cAppNewerSay', 'cAppSent', 'cAppOwns', 'cAppByHand', 'cMakeSecret', 'cImportPicked', 'cFormYaml', 'cFormWrote', 'openNewProject', 'openAddRepository', 'openNotebook', 'openPending', 'drawPendingModal', 'pendAct',
  'openProjectsTab', 'openSendToDocker', 'openTab', 'openTrash', 'pDraw',
  'nbDsRuleUI', 'nbDsKeyOf', 'nbDsPresets', 'nbDsByKey', 'nbDsPlatformOf', 'nbDsClone', 'nbDsHolderSlug', 'nbDsRo', 'nbDsLoadDesign', 'nbDsDrawHint', 'nbDsDrawAdd', 'nbDsFillTemplates', 'nbDsWireAdd', 'nbDsWriteFile', 'nbDsTouched', 'nbDsOpt', 'nbDsShown', 'nbDsDrawDesign', 'nbDsPick', 'nbDsChoice', 'nbDsCustomCells', 'nbDsThemesSection', 'nbDsRulesList', 'nbDsWireRulesList', 'nbDsThemeBand', 'nbDsLightHalf', 'nbDsPagesSection', 'nbDsPageSaid', 'nbDsPageBody', 'nbDsPaint', 'nbDsBlockStyle', 'nbDsRowsMax', 'nbDsFrameOf', 'nbDsReach', 'nbDsGridOf', 'nbDsBoardHtml', 'nbDsDescends', 'nbDsDepthOf', 'nbDsLayersHtml', 'nbDsMoveLayer', 'nbDsMoveTo', 'nbDsWireLayers', 'nbDsKindLabel', 'nbDsRepaintBoard', 'nbDsPageOption', 'nbDsClampBlock', 'nbDsFitIn', 'nbDsKidsOf', 'nbDsSettle', 'nbDsGeometry', 'nbDsToFrame', 'nbDsLayoutsAdd', 'nbDsLayoutsRemove', 'nbDsWirePage', 'nbDsWireBlocks', 'nbDsRemoveBlock', 'nbDsWireBoard', 'nbDsBoardPointerDown', 'nbDsBoardKeyDown', 'nbDsWireLanguage', 'nbDsFromScheme', 'nbDsWireThemes', 'nbDsWireThemeBand', 'nbDsSame', 'nbDsLangDirty', 'nbDsPagesDirty', 'nbDsClearStaged', 'nbDsCommitStaged', 'nbDsStageSections',
  'nbAnalysisView', 'nbArtifactsView', 'nbBugsView', 'nbDesignView', 'nbGitView', 'nbHistoryView', 'nbMemoryView', 'nbPendingView', 'chipsScrolled', 'chipsEdge', 'chipsEdges', 'chipsArrow', 'chipsDown', 'chipsMove', 'chipsUp', 'chipsClickGuard', 'dmHostOnly', 'nbPermsView', 'nbSessionsView', 'convRows', 'convForm', 'resumeConversation', 'rmLastSaid', 'rmLastModel', 'rmStartKeys', 'rmStartOn', 'nbRoadmapView', 'nbRulesView', 'nbSigningView', 'nbTestsView', 'nbWikiView', 'wikiMarkdown', 'wikiSlug', 'wikiToc', 'wikiNav', 'wikiUntitled', 'wikiContents', 'wikiScroll', 'wikiArticle', 'pullScroller', 'pullRefresh', 'wirePull', 'openReport', 'reportDrawForm', 'reportConvFor', 'sendReport', 'pDrawForge', 'pUrlHost', 'postJSON', 'unlinkProject',
  'nbRmLoad', 'nbRmCanSend', 'nbRmRowFacts', 'nbRmStepRow', 'nbRmBoxHolding', 'nbRmDraw', 'nbRmSendBoxEl', 'nbRmShutSendBoxes', 'nbRmDrawSendBox', 'nbRmPick', 'nbRmCancelSend', 'nbRmReallySend', 'nbRmPost', 'nbRmShowClash', 'nbRmSettleClash', 'nbRmDrawClash', 'nbRmOpenDrop', 'nbRmPickItem', 'nbRmOpenSplit', 'nbRmOpenReword', 'nbRmOpenStepInput', 'nbRmCloseStepInput', 'nbRmAdd', 'nbRmForm', 'nbRmRevertPending', 'nbRmStage', 'nbRmStageAdd', 'nbRmStageAddStep', 'nbRmStageEdit', 'nbRmStageInfo', 'nbRmStageTarget', 'nbRmStageRemove', 'nbRmStageShelve', 'nbRmMoveLocally', 'nbRmFlushPending', 'nbRmLoadFinished', 'nbRmDrawFinished', 'sayPost', 'poster',
  'pDrawForm', 'pFillNode', 'pDirOf', 'dmCalled', 'dmJobSettle', 'rnFillReads', 'rnLoadTools', 'rnFillTools', 'rnLockSettings', 'rnRowsList', 'rnHostIds', 'rnBars', 'rnDrawForms', 'rnWireBox', 'rnBarSay', 'rnRevertSect', 'rnSectChanges', 'rnEnc', 'rnDec', 'pJobAct', 'pJobPoll', 'pJobSeen', 'pJobWire', 'pNameShow', 'pOpen',
  // A terminal in its own window.
  'popOut', 'reattachTab',
  'pShowKey', 'pSlide', 'paginate', 'pageReach', 'onPress', 'patch', 'patchKey', 'patchSame', 'patchFieldOf', 'patchAttrs', 'patchRecord', 'patchWas', 'patchControl', 'patchNode', 'patchKids', 'patchOwn', 'patchHeld', 'patchInto', 'pressBack', 'drawFresh', 'takeAway', 'giveBack', 'onTyping', 'fieldsBack', 'paintBar', 'paneStack',
  'phFetch', 'tcAct', 'tcPick', 'packState', 'packMachineState', 'packHeldState', 'packVersionPill', 'packJobErr', 'toolchainsSeen', 'toolchainsFor', 'tcOn', 'packDeploy', 'agentUpdate',
  // The Emulator tab (tab-emulator.js).
  'openEmulator', 'emuPick', 'loadEmulator', 'emuAddRows', 'emuFlavorNow', 'emuTickedHere', 'emuRow', 'renderEmulatorInto', 'emuAct', 'tcTermsLine', 'tcVerifiedLine', 'tcReceiptLines', 'tcHeldLine', 'tcSystemLine', 'tcNeedsLine', 'tcDriverLine', 'tcDriverOption', 'tcToolkitLine', 'nodesReadOnly', 'headerOnly', 'popoutFocus', 'splitSects', 'splitDraw', 'splitAway', 'bootOwn', 'splitMove', 'splitMarks', 'splitOff', 'rnSplit', 'rolesInsts', 'rolesLvlAt', 'rolesSetAll', 'viewSaid', 'pageKey', 'pageLimit', 'rnPrefsOf',
  // The Claude sign-in on a node's row (page-signin.js), and the press that goes to it.
  'signinRev', 'signinCannot', 'signinBusy', 'signinBlock', 'wireSignin', 'openNodeClaude', 'signinCancel', 'claudeSigninFirst', 'claudeNodes', 'claudeEnd', 'modalTop', 'keepOpen', 'keepLine', 'pollRevsOnce', 'oneOpen', 'sectGroup', 'soleShut', 'soleOpen', 'sectJump', 'sectGoTo', 'formBox', 'formField', 'topModal', 'modalOpened', 'modalClosed', 'modalFocusables', 'dismissModal', 'modalWayOut', 'backHold', 'backRelease', 'backPressed', 'hashGo', 'dmBackHold', 'dmBackLet', 'modalKeys', 'scrollHint', 'scrollHints', 'hintSoon',
  'nodeGpuSection', 'nodeSound', 'nodeInternet', 'ndOffLine', 'ndNotHereHtml', 'tcTickDots',
  'claudeNodeFacts', 'placeResumeMenu', 'resumeButton', 'closeResumeMenu', 'rmPut', 'rmTitle', 'pollRevs', 'restartSeen', 'restartKeep', 'restartKept', 'restartScrollTo', 'restartScrollBack', 'awayCalm', 'awaySay', 'awayQuiet', 'awayEnd', 'unsavedHere', 'readFailed', 'wireReadAgain', 'typedField', 'typedWatch', 'formTyped', 'leaveOnPurpose', 
  'phoneWhy', 'dmBootLine', 'dmLanLine', 'nodePick', 'fitPickers', 'fitHeadPickers', 'fitPickersSoon', 'openRunnerTab', 'renderPhoneInto', 'renderRunnerInto', 'phoneRowPress', 'openPhoneLend', 'openProjectSettings', 'openSpaceSettings', 'settingsInto', 'settingsOut', 'pushLayout', 'readLocalPanes', 'keepLocalPanes', 'quietFields', 'reapDeadTerminals',
  'reattachTerminals', 'openFindingsTab', 'openJobsTab', 'openSchedulesTab', 'openDebugTab', 'debugGrant', 'renderDebugInto', 'wireDebug', 'loadSchedules', 'postSchedule', 'schedWhen', 'schedRow', 'schedForm', 'schedAs', 'openSchedForm', 'closeSchedForm', 'wireSchedForm', 'renderSchedulesInto', 'wireSchedules', 'openNodesTab', 'openSettingsTab', 'settingsKeep', 'settingsWake', 'loadReports', 'deleteReport', 'gitLanes', 'renderDiff',
  'openPhoneTab', 'phonePanel', 'wirePhoneTab',
  'openStorageTab', 'loadStorage', 'storageHeld', 'storageRow', 'andList', 'storageDisks', 'storageMachineDisks', 'movePools', 'moveLandOpts', 'moveMoverOpts', 'moveSaid', 'moveFields', 'moveRead', 'storageShares', 'wireStorageShares', 'storagePools', 'wireStoragePools', 'storageSnapshots', 'wireStorageSnapshots', 'storageArray', 'storageAdopt', 'arrayVerifyWord', 'wireStorageArray', 'storageOther', 'wireStorageOther', 'storageBackups', 'wireStorageBackups', 'storageProjects', 'storageBody', 'storagePick', 'renderStorageInto', 'wireStorageTab',
  'maintAsk', 'openKeysTab', 'postKeys', 'loadKeys', 'keysNotices', 'keysInstallBody', 'keysKeptBody', 'renderKeysInto', 'keysGo', 'keysChange', 'wireKeys',
  'loadKeyMine', 'keyMineSection', 'keyStorePurge', 'wireKeyMine', 'keyStoreHeld', 'keyStoreSecret', 'keyStoreUnlock', 'keyStoreOwn', 'keyStoreNewKey',
  'openAuditTab', 'loadAudit', 'openNetworkTab', 'networkReach', 'networkDialStatus', 'networkDial', 'renderNetworkInto', 'openMachineTab', 'ownMachine', 'machinesLive', 'machinesNode', 'liveAgents', 'keptNode', 'openKindOn', 'machinesActions', 'pnotePutAway', 'groupKept', 'groupKeep', 'groupNode', 'groupPick', 'toolOff', 'groupHeader', 'openNodePage', 'wireGroupHeader', 'machineHead', 'renderMachineInto', 'wireHeld', 'firstbootSection', 'adoptFound', 'adoptSection', 'adoptBackSection', 'adoptSharesLine', 'adoptFolders', 'adoptFoldersField', 'adoptMovesNow', 'adoptTakeField', 'wireAdopt', 'adoptAppsSection', 'oldAppsFrom', 'adoptAppsPointer', 'loadAdoptPlan', 'wireAdoptApps', 'machineConsoleSection', 'setupTopActs', 'consoleLogin', 'setupGenerateConsole', 'setupShutDown', 'ownNodeAt', 'machineNodeSections', 'wireMachineConsole', 'holdNextBox', 'wireHoldNext', 'stickSection', 'projectsFolderField', 'wireStick', 'olderVersionsSection', 'wireOlderVersions', 'ndRowHtml', 'nodeMachineSection', 'nodePowerSection', 'nodeReportSection', 'loadHistory', 'wireReportSection', 'wireMachineSection', 'drawHeldBand', 'auditRows', 'renderAuditInto', 'wireAudit',
  'connectionIntro', 'connectionStatus', 'updatesSection', 'loadRootHooks', 'rootHooksWaiting', 'rootHooksSection', 'connSection', 'connStatus', 'connDue', 'connGo', 'loadConnections', 'wireConnections', 'wireRootHooks', 'loadBackup', 'backupSection', 'wireBackup', 'wireUpdates', 'loadMove', 'moveStatus', 'moveSize', 'moveSection', 'wireMove', 'drawMovedBand', 'nginxAcmeLines',
  'usbHolder', 'usbWords', 'nodeUsbSection', 'wireUsbSection',
  'openScannersTab', 'loadScanners', 'scannersAct', 'scannersVersions', 'scannersLastRun', 'scannersNodeSection', 'scannersScheduleSection', 'scannersUncovered', 'scannersActs', 'renderScannersInto', 'wireScannersTab',
  'tourSeen', 'tourSoon', 'tourRetry', 'tourLoading', 'tourSample', 'tourSampleProject', 'tourFlip', 'tourSampleCard', 'tourTarget', 'tourStart', 'tourKeepSample', 'tourDraw', 'glanceWaiting', 'tourGo', 'tourEnd', 'tourLeft', 'tourReset', 'rnVmCapsOf', 'rnVmCapsNow', 'rnVmCapsSet', 'openVmsTab', 'loadVms', 'vmPill', 'vmRow', 'nodeFeaturesSection', 'vmGroupsHtml', 'vmOthersHtml', 'vmCloneAsk', 'vmBar', 'renderVmsInto', 'wireVms', 'openNewVm', 'vmHwLine', 'vmHwFields', 'vmNetOptions', 'vmNewMac', 'vmNetFields', 'vmHwRead', 'vmHwWire', 'openVmHardware', 'vmConsolesChecked', 'vmReapConsoles',
  'openNginxTab', 'loadNginx', 'nginxKeepTyping', 'projectHeader', 'wireProjectHeader', 'wireProjectMenu', 'reposAlso', 'projectState', 'claudeDeadWhy', 'agentInstall', 'projectNote', 'projectActions', 'projectMatches', 'lockMark', 'projFacts', 'projectCard', 'reposOf', 'projectList', 'cardMarks', 'cardLock', 'cardFront', 'projNotes', 'cardBack', 'flipCard', 'newProjectByName', 'renameProjectCard', 'renameRepository', 'moveRepository', 'deleteProjectCard', 'wireProjectCards', 'agentButton', 'fxRemember', 'projectJobHtml', 'dockKeep', 'dockPlace', 'dockSettle', 'dockShow', 'dockToggle', 'dockBar', 'dockSpend', 'wireDockBar', 'dockReveal', 'dockEdges', 'dockDress', 'toggleDoctor', 'runnerRows', 'exposedOf', 'dmShellWhy', 'dmShell', 'openHome', 'homeOpen', 'loadHome', 'homeUpdates', 'homeTiles', 'homeTilesHtml', 'homeHref', 'homeJobsHtml', 'homeGlanceHtml', 'homeAttention', 'renderHomeInto', 'needsRows', 'wireNeeds', 'openJob', 'toastPlace', 'toastAdd', 'toastTick', 'toastHold', 'toastGone', 'tblTracks', 'tblWrap', 'viewSeg', 'dmStatsPatch', 'dmNoteOpen', 'dmSyncDialogs', 'holdPanes', 'cHold', 'vmTiles', 'vmChipGroups', 'tblLine', 'jobNode', 'jobTook', 'jobBy', 'sparkSvg', 'hourChart', 'wireCharts', 'nodeCharts', 'setText', 'setAttr', 'setClass', 'setHidden', 'setDisabled', 'setTitle', 'statusLater', 'dmLineWrap', 'dmLineCells', 'dmOtherWrap', 'keepNotice', 'askTag', 'askCmd', 'askLeft', 'askWho', 'askActs', 'askAnswer', 'askLong', 'askEnded', 'notifyJob', 'toastWhy', 'jobToastsCheck', 'openNotices', 'loadNotices', 'noticesAct', 'noticesAskRows', 'noticesWaitingRows', 'noticesShown', 'renderNoticesInto', 'wireNotices', 'resumeHostNow', 'syncResumeMenu', 'nginxAct', 'nginxTls', 'nginxSite', 'nginxRouteForm', 'nginxRoutesTable', 'nginxCertPick', 'nginxResolve', 'nginxCertLines', 'nginxRedraw', 'nginxDraftOf', 'nginxBody', 'ngSect', 'nginxPick', 'renderNginxInto', 'nginxReadDraft', 'wireNginxTab',
  // The welcome panel (the About popup grown a guide and the changelog). The
  // guides are top-level consts, which are not window properties.
  'abShow', 'abGuideText', 'abLoadGuide', 'abLoadLog', 'abDrawCredits', 'abDrawLog', 'openAbout', 'closeAbout', 'welcomeOnce', 'updatedShow', 'updatedElsewhere', 'updatedHide',
  'proseline', 'proselines',
  // One way for a press to send and say, one for a read, one for a draw's
  // arrival, and boot's parts.
  'answerOf', 'limitedFetch', 'boot', 'bootAway', 'bootContainerDialogs', 'bootCreating', 'bootDockDrag', 'bootDocs', 'bootDoctor',
  'bootFindings', 'bootFirstSession', 'bootKeys', 'bootLast', 'bootLogs', 'bootMarkup', 'bootMenuHeld',
  'bootMoreMenus', 'bootMotion', 'bootPickers', 'bootNewProject', 'bootNotebooks', 'bootNotices', 'bootPanes',
  'bootProjectSettings', 'bootShell', 'bootTabs', 'bootTermWindow', 'bootWaits', 'bootWatches', 'bootWelcome',
  'chipsBack', 'dockerImagesRead', 'dockerStatsRead', 'drawHTML', 'drawn', 'getJSON', 'phLanded', 'phRead', 'phSend',
  'nodesKnown', 'postFile', 'pressHook', 'pressOf', 'pressQuiet', 'pressRun', 'pressTie', 'readFor', 'readKept', 'readMoved', 'readSettle', 'nodeOf', 'nodeNameOf', 'sessionsOn', 'sessionsEndSaid', 'ndPowerSaid',
  'reading', 'readingOf', 'sayUnheard', 'wireRead',
  // The Users tab (roadmap #22 step 3). Functions only: a top-level `let`
  // is not a window property, so usersList and friends are not listed here.
  'openUsersTab', 'loadUsers', 'usersAct', 'userRow', 
  'fxFilter', 'fxRows', 'renderUsersInto', 'wireUsers', 'usersEditFrom', 'usersPicked', 'usersDirty', 'usersRedraw', 'usersReadOnly', 'usersDetail', 'wireUsersBar', 'usersSave', 'usersAddOpen', 'rolesAccessFields', 'wireRolesAccess', 'rolesAccessSave', 'rolesAccessOpen', 'rolesNewOpen', 'openRolesTab', 'loadRoles', 'rolesAct', 'rolesFrom', 'rolesCanDo', 'rolesPeopleDirty', 'rolesPeopleFrom', 'rolesPerson', 'rolesRedraw', 'rolesRoleBody', 'rolesRoleDirty', 'renderRolesInto', 'wireRoles', 'openProfileTab', 'loadProfile', 'renderProfileInto', 'wireProfile', 'openConversation', 'wireDeviceOut', 'profileTwoFactor', 'pfTf', 'pfFresh', 'wireTwoFactor', 'openProfileTwoFactor', 'loadApps', 'appsIntro', 'appsStatus', 'checksIntro', 'checksStatus', 'wireChecks', 'catalogIntro', 'catalogStatus', 'wireCatalogMirror', 'devHow', 'renderFindingsInto', 'flRows', 'fxBarHtml', 'fxBarBand', 'fxWireBar', 'reportAges', 'refresh', 'refreshSoon', 'renameProject', 'rnDialsHome', 'rnSpaceMarks', 'rnSpaceRelock', 'rnFillHostsOwn', 'rnDialApart', 'rnFillTests', 'render',
  'idleSection', 'wireIdleSection', 'pathsSection', 'wirePathsSection', 'settingsSections', 'withRevert', 'tunnelSteps', 'tunnelStatus', 'tunnelNodes', 'wireSettingsSections', 'settingsLive', 'settingsFacts', 'settingsPaintFacts', 'settingsChecks', 'settingsPaintDoctor', 'settingsCardSaid', 'settingsCard',
    'reportsSection', 'clearReports',
  'renderDoc', 'renderDockerInto', 'renderGuarded', 'typingIn', 'typingBack', 'renderJobsInto', 'renderNodesInto', 'renderNotebookInto', 'renderSettingsInto',
  'renderProjectsInto', 'repoOfUrl',
  // The Library: its functions (a let or a const is no property of the window).
  'openLibrary', 'openLibraryOn', 'libPick', 'loadLibrary', 'railWarm', 'dockerWarm', 'libKnown', 'libFind', 'libQuery', 'libAddr', 'libFromAddr', 'libMore', 'libPagesFrom', 'libReload', 'libPills', 'makerLine', 'libState', 'libActs', 'libDetail', 'libRow',
  'libFilterBand', 'libViewNow', 'libNarrowed', 'libPackNote', 'libHostNote', 'libCards', 'rnLoadDiscord', 'rnDrawDiscord', 'nbDiscordLoad', 'nbDiscordDraw', 'nbDiscordAct', 'libShelves', 'libList', 'renderLibraryInto', 'wireLibrary', 'libWithToolchains', 'libAct', 'libLook', 'libDriverPick',
  'openNewContainerApp', 'tpAppCells', 'tpAppSeen', 'tpAppLook', 'tpOpenApp', 'tpWhatCell', 'openFilesTab', 'flPick', 'flQuery', 'loadFiles', 'flGo', 'flSize', 'flCrumbs', 'flRows', 'flLine', 'renderFilesInto', 'flFull', 'flPost', 'wireFiles', 'flAct', 'flUpload', 'flPreview', 'openInstalledTab', 'openInstalledOn', 'instPick', 'loadInstalled', 'instHere', 'instState', 'instActs', 'instConfigField', 'instConfigForm', 'instConfigRead', 'instServiceLines', 'instRow', 'renderInstalledInto', 'wireInstalled', 'instAct', 'instOpen',
  'reschedRevs', 'rnDrawAuth', 'rnDrawKey', 'rnDrawStore', 'rnKeyAct', 'drawSetup', 'setupCard', 'setupWalking', 'setupWalkArrive', 'setupPlaceSig', 'setupPlaceCard', 'setupPlaceAuto', 'setupInTurn', 'setupHoldCard', 'setupInOrder', 'setupSharesCard', 'setupWalkPick', 'setupLandLoad', 'setupWalkSig', 'setupBootBack', 'setupWalkHtml', 'stickPoolPick', 'adoptParts', 'adoptDegradedSaid', 'moveLandBox', 'moveBundleAge', 'setupFinish', 'setupNeeded', 'setupNode', 'setupOwn',
  'rnDrawPeople', 'rnDrawPrefs', 'rnFolds', 'rnTestAuth', 'rnLoadFtp', 'rnDrawReach', 'rnReachNodes', 'rnReachNow', 'rnReachSave', 'rnFtpWhere', 'rnDrawFtp', 'rnFtpChange', 'rnSaveFtp', 'rnFillNode', 'rnFillNodesMore', 'rnMoreIds', 'rnMoreSave', 'rnDrawRelFiles', 'rnSaveRelFiles', 'rnFillPrefs', 'rnFillTestNode', 'rnFillPrefsRest', 'rnLoadAuth', 'rnLoadPeople', 'rnWhyOff', 'rnLoadSnapshots', 'rnDrawSnapshots', 'rnSavePeople', 'rnSessionEnd', 'rnSessionsDraw', 'rnSessionsLoad', 'rnFolderLine', 'ghName', 'rnShow', 'rnSubmit',
  'roomForTab', 'saveLayout', 'sendCode', 'sendKey',
  'sessionLabels', 'sessionOf', 'ask', 'askText', 'askTyped', 'askYes', 'askQuestion', 'askYesWord', 'setArchived', 'setBadge', 'setLocked', 
  'setProjectPinned', 'shortUptime', 'shortUptime', 'show', 'showInStack', 'holdLeaving',
  'signIn', 'signOut', 'slideDetails', 'foldOpen',
  'slideHidden', 'fadeIn', 'ghostOf', 'ghostOut', 'fadeThrough', 'moveKey', 'onScreen', 'chipMove', 'slideMark', 'swapBox', 'startClaude', 'sendSure', 'launchClaude',   'openBrief', 'closeBrief', 'briefDrawForm', 'briefGo', 'pArchivePicked',
  'tabLabel', 'tabLabels', 'tabTitle', 'untitle', 'untitleIn', 'helpToggle', 'helpShow', 'helpHide', 'cLock', 'dmUnrouted', 'nodeDoorConfig', 'nginxUndeployed', 'resumePicker', 'toggleBell', 'toggleUiMenu', 'unveil', 'watchSignin', 'wireConsole', 'wireLogSection', 'wireJobsTab', 'wireNodeConf', 'wireNodesTab', 
  'wireProjectRows',
  // A press drawn on the click: the spaces' marks and
  // deletes, a session ended, a report, a profile row, a sent message.
  'projHeldLay', 'projMarkNow', 'trashList', 'sessEndNow', 'sessEndRead', 'sessShown', 'agentTab',
  'reportsGone', 'pfReachNow', 'pfGone', 'pfDeviceGone', 'pfTfNow', 'chatShown',
  // ...and a press the server queues behind a running job says so.
  'sysJobAhead', 'sysSaid', 'setupAhead'
];

const browser = await launch();
const page = await newPage(browser);
await page.goto(URL);
await ready(page);

// Measured against a fresh iframe's window rather than a hardcoded list of
// browser builtins, so a Chromium upgrade adding an API does not read as the
// page growing a global.
const live = await page.evaluate(() => {
  const f = document.createElement('iframe');
  f.style.display = 'none';
  document.body.appendChild(f);
  const base = new Set(Object.getOwnPropertyNames(f.contentWindow));
  f.remove();
  return Object.getOwnPropertyNames(window)
    .filter(k => !base.has(k) && !/^\d+$/.test(k) && !k.startsWith('__bbcov')).sort();  // the coverage counters, under aerie tests coverage
});

const declared = new Set(SURFACE);
const seen = new Set(live);
const missing = SURFACE.filter(n => !seen.has(n));
const added = live.filter(n => !declared.has(n));

ok(missing.length === 0,
   `every name the page declares at the top level is still there${
     missing.length ? `; missing: ${missing.join(', ')}` : ''}`);
ok(added.length === 0,
   `and nothing has quietly become a global${
     added.length ? `; new: ${added.join(', ')}` : ''}`);

// The ones other code reaches for by name: the inline handlers in the markup
// and the suite's own page.evaluate calls. Named separately because a generic
// "the list matches" failure does not say which of them the page just lost.
const REACHED = ['refresh', 'openTab', 'hideTab', 'tabOf', 'sessionOf',
                 'newShell', 'setProjectPinned', 'renameProject', 'drawProjects',
                 'renderSessionsInto', 'drawBell', 'notify', 'openTrash', 'drawTrash',
                 'patch', 'drawUiMenu', 'toggleBell'];
// By bare name, not through window: half of these are `const` arrows, which
// are in the global lexical scope and never become window properties. The
// question being asked is "can other code call this", and that is the form
// other code uses.
const kinds = await page.evaluate(names => names.map(n => {
  try{ return [n, new Function(`return typeof ${n}`)()]; }
  catch(e){ return [n, 'unreachable']; }
}), REACHED);
const notFn = kinds.filter(([, t]) => t !== 'function').map(([n]) => n);
ok(notFn.length === 0,
   `the names the markup and the suite call are callable at the top level${
     notFn.length ? `; not: ${notFn.join(', ')}` : ''}`);

// Every name a script reads or writes is declared at the top level of some
// script the page loads, or is the browser's. Code moved into a view file
// keeps calling what it called before, and a name that stayed behind in the
// closure it came from is a ReferenceError the first time that path runs;
// a bare WRITE to one is worse, a stray global and no error at all. Four
// did exactly that on 16 Sep, on paths no suite happened to press. This is a
// read of the source rather than a run of it: Babel's scope tracker, which
// Playwright carries, resolves every reference to its binding.
const DASH = join(dirname(fileURLToPath(import.meta.url)), '..');
const { babelParse, traverse } = createRequire(import.meta.url)('playwright/lib/transform/babelBundle');
const html = readFileSync(join(DASH, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script(?: src="([^"]+)")?>([\s\S]*?)<\/script>/g)].map(m => m[1]
  ? {file: m[1], code: readFileSync(join(DASH, m[1]), 'utf8'), base: 0}
  : {file: 'index.html', code: m[2], base: html.slice(0, m.index).split('\n').length - 1});
const browserNames = await page.evaluate(() => {
  const f = document.createElement('iframe');
  f.style.display = 'none';
  document.body.appendChild(f);
  const names = new Set();
  for (let o = f.contentWindow; o; o = Object.getPrototypeOf(o))
    Object.getOwnPropertyNames(o).forEach(k => names.add(k));
  f.remove();
  return [...names];
});
const known = new Set(browserNames), uses = [], whose = new Map();
for (const s of scripts)
  traverse(babelParse(s.code, s.file.replace(/\.html$/, '.js'), false), {Program(p){
    Object.keys(p.scope.bindings).forEach(n => { known.add(n); whose.set(n, [...(whose.get(n) || []), s.file]); });
    for (const [n, node] of Object.entries(p.scope.globals))
      uses.push({n, at: `${s.file}:${s.base + (node.loc?.start.line || 0)}`});
    p.stop();
  }});
const stray = uses.filter(u => !known.has(u.n)).map(u => `${u.n} (${u.at})`);
ok(scripts.length > 2 && known.size > 500 && stray.length === 0,
   `every name the page's ${scripts.length} scripts use is declared by one of them or is the browser's${
     stray.length ? `; declared nowhere: ${stray.join(', ')}` : ''}`);

// One name, one script. A `function` declared at the top level of two
// classic scripts is one global, and the later script's quietly replaces the
// earlier's: page-dock.js's placeTab took page-tabstrip.js's drag helper's
// name on 14 Oct, and only a suite's TypeError said so. (A `let` or `const`
// declared twice is a SyntaxError on load, which zero console errors holds.)
const twice = [...whose].filter(([, fs]) => fs.length > 1).map(([n, fs]) => `${n} (${fs.join(', ')})`);
ok(twice.length === 0,
   `no top-level name is declared by two scripts${twice.length ? `; declared twice: ${twice.join('; ')}` : ''}`);

// The other half of that seam. A view reaches the notebook's helpers and the
// other views through the state object (nb.syncSave(), nb.shutSendBoxes), so
// a name one view stops handing back, or a helper the closure stops putting
// there, is a TypeError on some later click rather than a ReferenceError
// anybody can see by name. Every nb.NAME read must be put on nb by an
// assignment, by Object.assign's literal, or by the return of a view factory
// that is assigned to it. The state is the nb of makeNotebook, of a view, or
// of a function a view is cut into: any function or const arrow named nb...
// whose own nb it is, so a put or a read moved out of a view's closure still
// counts. A row of NB_VIEWS is handed it too: what a view loads and watches
// is an arrow in the table.
const isState = p => {
  const fn = p.scope.getBinding('nb')?.scope.path;
  const name = fn?.node.type === 'FunctionDeclaration' ? fn.node.id?.name
    : fn?.parentPath?.isVariableDeclarator() ? fn.parent.id.name
    : fn?.findParent(q => q.isVariableDeclarator())?.node.id.name === 'NB_VIEWS' ? 'nbViews' : '';
  return /^(makeNotebook|nb\w+)$/.test(name || '');
};
const put = new Set(), reads = [], hands = {}, assignedFrom = [];
for (const s of scripts)
  traverse(babelParse(s.code, s.file.replace(/\.html$/, '.js'), false), {
    FunctionDeclaration(p){
      if (!/^nb\w+View$/.test(p.node.id.name)) return;
      const ret = p.node.body.body.findLast(st => st.type === 'ReturnStatement');
      hands[p.node.id.name] = (ret?.argument?.properties || []).map(q => q.key.name);
    },
    CallExpression(p){
      const c = p.node.callee, [target, from] = p.node.arguments;
      if (c.type !== 'MemberExpression' || c.object.name !== 'Object' || c.property.name !== 'assign'
          || target?.type !== 'Identifier' || target.name !== 'nb' || !isState(p)) return;
      if (from?.type === 'ObjectExpression') from.properties.forEach(q => put.add(q.key.name));
      if (from?.type === 'CallExpression' && from.callee.type === 'Identifier') assignedFrom.push(from.callee.name);
    },
    MemberExpression(p){
      const n = p.node;
      if (n.computed || n.object.type !== 'Identifier' || n.object.name !== 'nb' || !isState(p)) return;
      if (p.parentPath.isAssignmentExpression() && p.parent.left === n) put.add(n.property.name);
      else reads.push({n: n.property.name, at: `${s.file}:${s.base + n.loc.start.line}`});
    },
  });
assignedFrom.forEach(f => (hands[f] || []).forEach(n => put.add(n)));
const unput = [...new Set(reads.filter(r => !put.has(r.n)).map(r => `nb.${r.n} (${r.at})`))];
ok(reads.length > 100 && assignedFrom.length > 5 && unput.length === 0,
   `every one of the ${reads.length} reads of the notebook's state finds a name something puts there${
     unput.length ? `; put nowhere: ${unput.join(', ')}` : ''}`);

// The notebook's views, one list. NB_VIEWS in nb-core.js is what the first
// paint's strip, a view's loads and its watches are read from; the strip
// itself is static markup in the notebook's template, there before any
// script has run on it, so it is held to the table here, from the source:
// the same groups in the same order under the same words, each group's
// views in the table's order under theirs, and a pane for every view.
const lit = n => n?.type === 'StringLiteral' ? n.value : null;
const table = {};
traverse(babelParse(readFileSync(join(DASH, 'nb-core.js'), 'utf8'), 'nb-core.js', false), {Program(p){
  for (const name of ['NB_GROUPS', 'NB_VIEWS'])
    table[name] = (p.scope.bindings[name]?.path.node.init?.elements || []).map(e => e.type === 'ArrayExpression'
      ? e.elements.map(lit)
      : Object.fromEntries(e.properties.filter(q => lit(q.value) !== null).map(q => [q.key.name, q.value.value])));
  p.stop();
}});
const strip = /<div class="nbtabs"[^>]*>\s*<div class="nbgroups[^>]*>([\s\S]*?)<\/div>\s*<div class="nbsub[^>]*>([\s\S]*?)<\/div>/.exec(html) || [];
const stripGroups = [...(strip[1] || '').matchAll(/<button type="button" data-g="([^"]+)">([^<]*)<\/button>/g)].map(m => [m[1], m[2]]);
const stripViews = [...(strip[2] || '').matchAll(/<button type="button" data-v="([^"]+)" data-in="([^"]+)">([^<]*)<\/button>/g)]
  .map(m => ({key: m[1], group: m[2], label: m[3]}));
const viewPanes = [...html.matchAll(/<div class="nbview[^"]*" data-view="([^"]+)"/g)].map(m => m[1]);
const rowOf = (list, g) => list.filter(v => v.group === g).map(v => `${v.key} "${v.label}"`).join(', ');
const offStrip = [];
if (JSON.stringify(stripGroups) !== JSON.stringify(table.NB_GROUPS))
  offStrip.push(`the groups are ${JSON.stringify(stripGroups)}, the table's ${JSON.stringify(table.NB_GROUPS)}`);
for (const [g] of table.NB_GROUPS)
  if (rowOf(stripViews, g) !== rowOf(table.NB_VIEWS, g))
    offStrip.push(`${g} is ${rowOf(stripViews, g) || 'empty'}, the table's ${rowOf(table.NB_VIEWS, g) || 'empty'}`);
// A button the two patterns did not read, a view in a group the table does
// not have, a key written twice: none of which the rows above would show.
if (((strip[1] || '') + (strip[2] || '')).split('<button').length - 1 !== stripGroups.length + stripViews.length
    || stripViews.length !== table.NB_VIEWS.length || new Set(table.NB_VIEWS.map(v => v.key)).size !== table.NB_VIEWS.length
    || table.NB_VIEWS.some(v => !table.NB_GROUPS.some(([g]) => g === v.group)))
  offStrip.push(`the markup has ${stripViews.length} view buttons and the table ${table.NB_VIEWS.length} views, which are to be the same ones, each once and in one of the groups`);
if ([...viewPanes].sort().join() !== table.NB_VIEWS.map(v => v.key).sort().join())
  offStrip.push(`the panes are ${viewPanes.join(', ')}`);
ok(table.NB_GROUPS.length === 5 && table.NB_VIEWS.length >= 15 && offStrip.length === 0,
   `the notebook's strip in the markup is NB_VIEWS: ${table.NB_GROUPS.length} groups, ${table.NB_VIEWS.length} views in their rows, a pane each${
     offStrip.length ? `; not so: ${offStrip.join('; ')}` : ''}`);

ok(page.errors.length === 0, 'zero console errors');
if (page.errors.length) console.log(page.errors);
await done(browser);
