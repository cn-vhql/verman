use anyhow::Result;
use slint::{LogicalSize, ModelRc, SharedString, VecModel};
use std::cell::RefCell;
use std::rc::Rc;
use verman_core::{
    AppSettings, ChangeStatus, VersionDetails, VersionDiffResult, VersionFilePreview, WorkspaceData,
};
use verman_engine::Engine;
use verman_platform_windows::explorer_integration_status;

slint::slint! {
import { VerticalBox, HorizontalBox, ListView, ComboBox, TextEdit } from "std-widgets.slint";

export struct PreviewLine {
    text: string,
    highlight: bool,
}

component ToolbarButton inherits Rectangle {
    in property <string> label;
    in property <bool> primary: false;
    callback tapped();
    height: 32px;
    min-width: 88px;
    border-width: 1px;
    border-color: primary ? #6c87ad : #9aa6b6;
    background: primary ? #dce8f6 : #f3f5f7;
    Text { text: root.label; color: #1f2833; horizontal-alignment: center; vertical-alignment: center; }
    TouchArea { clicked => { root.tapped(); } }
}

component ActionButton inherits Rectangle {
    in property <string> label;
    in property <bool> primary: false;
    in property <bool> danger: false;
    callback tapped();
    height: 32px;
    min-width: 112px;
    border-width: 1px;
    border-color: danger ? #bf6a6a : primary ? #6c87ad : #9aa6b6;
    background: danger ? #f7dede : primary ? #dce8f6 : #f3f5f7;
    Text {
        text: root.label;
        color: danger ? #7c2222 : #1f2833;
        horizontal-alignment: center;
        vertical-alignment: center;
    }
    TouchArea { clicked => { root.tapped(); } }
}

component GroupFrame inherits Rectangle {
    in property <string> title;
    border-width: 1px;
    border-color: #b7c0cb;
    background: #fcfcfd;
}

component SummaryCard inherits Rectangle {
    in property <string> label;
    in property <string> value;
    in property <string> detail;
    border-width: 1px;
    border-color: #c7d0db;
    background: #f9fbfd;
    min-width: 150px;
    min-height: 84px;

    VerticalBox {
        padding: 10px;
        spacing: 2px;
        Text { text: root.label; color: #5a6a7d; font-size: 11px; }
        Text { text: root.value; color: #243244; font-size: 20px; font-weight: 700; }
        Text { text: root.detail; color: #6a798a; font-size: 11px; wrap: word-wrap; }
    }
}

component SettingRow inherits Rectangle {
    in property <string> title;
    in property <string> description;
    in property <string> value;
    callback tapped();
    border-width: 1px;
    border-color: #c7d0db;
    background: #fbfcfe;
    min-height: 64px;

    HorizontalBox {
        padding: 10px;
        spacing: 10px;
        VerticalBox {
            horizontal-stretch: 1;
            spacing: 3px;
            Text { text: root.title; color: #243244; font-size: 13px; font-weight: 700; }
            Text { text: root.description; color: #5a6a7d; font-size: 11px; wrap: word-wrap; }
        }
        ActionButton {
            label: root.value;
            primary: true;
            min-width: 132px;
            tapped => { root.tapped(); }
        }
    }
}

export component AppWindow inherits Window {
    callback open_workspace_requested();
    callback refresh_requested();
    callback create_version_requested();
    callback submit_create_requested();
    callback details_requested();
    callback compare_requested();
    callback rollback_requested();
    callback settings_requested();
    callback perform_compare_requested();
    callback close_details_requested();
    callback close_compare_requested();
    callback close_settings_requested();
    callback close_create_requested();
    callback close_rollback_requested();
    callback rollback_confirmed();
    callback toggle_language_requested();
    callback toggle_backup_requested();
    callback version_row_clicked(index: int);
    callback detail_file_clicked(index: int);
    callback open_selected_file_requested();

    in property <bool> is_english;
    in property <string> workspace_path;
    in property <string> project_summary;
    in property <string> health_fingerprint;
    in property <string> integration_summary;
    in property <string> integration_detail;
    in property <string> status_title;
    in property <string> status_body;
    in property <string> language_label;
    in property <string> backup_label;
    in property <[string]> change_rows;
    in property <[string]> version_rows;
    in property <string> total_files;
    in property <string> total_versions;
    in property <string> changed_files;
    in property <string> ignore_rule_count;
    in property <int> selected_version_index;
    in property <bool> create_visible;
    in-out property <string> create_description;
    in property <bool> details_visible;
    in property <string> details_title;
    in property <string> details_meta;
    in property <string> details_stats;
    in property <[string]> detail_rows;
    in property <int> selected_detail_index;
    in property <string> preview_left_label;
    in property <string> preview_right_label;
    in property <[PreviewLine]> preview_left_lines;
    in property <[PreviewLine]> preview_right_lines;
    in property <bool> preview_is_text;
    in property <string> preview_note;
    in property <bool> compare_visible;
    in property <string> compare_title;
    in property <string> compare_summary;
    in property <[string]> compare_rows;
    in property <[string]> compare_version_options;
    in-out property <int> compare_left_index;
    in-out property <int> compare_right_index;
    in property <bool> settings_visible;
    in property <string> settings_title;
    in property <string> settings_body;
    in property <bool> rollback_visible;
    in property <string> rollback_title;
    in property <string> rollback_body;

    title: "VerMan RS2";
    width: 1040px;
    height: 760px;
    background: #e8edf3;

    Rectangle {
        x: 8px;
        y: 8px;
        width: parent.width - 16px;
        height: parent.height - 16px;
        background: #eef2f6;
        border-width: 1px;
        border-color: #b7c0cb;

        VerticalBox {
            padding: 10px;
            spacing: 8px;

            Rectangle {
                height: 38px;
                background: #dde5ee;
                border-width: 1px;
                border-color: #b7c0cb;

                HorizontalBox {
                    padding: 4px;
                    spacing: 6px;
                    ToolbarButton { label: root.is_english ? "Project" : "项目"; primary: true; tapped => { root.open_workspace_requested(); } }
                    ToolbarButton { label: root.is_english ? "Refresh" : "刷新"; tapped => { root.refresh_requested(); } }
                    ToolbarButton { label: root.is_english ? "Version" : "版本"; tapped => { root.create_version_requested(); } }
                    ToolbarButton { label: root.is_english ? "Compare" : "对比"; tapped => { root.compare_requested(); } }
                    ToolbarButton { label: root.is_english ? "Settings" : "设置"; tapped => { root.settings_requested(); } }
                    Rectangle { horizontal-stretch: 1; }
                    Text { text: root.is_english ? "VerMan RS2 Preview" : "VerMan RS2 预览"; color: #243244; font-size: 20px; font-weight: 700; vertical-alignment: center; }
                }
            }

            Rectangle {
                height: 112px;
                background: #e3ebf3;
                border-width: 1px;
                border-color: #c3ccd7;

                HorizontalBox {
                    padding: 10px;
                    spacing: 10px;

                    VerticalBox {
                        horizontal-stretch: 1;
                        spacing: 3px;
                        Text {
                            text: root.is_english ? "Workspace Overview" : "工作区概览";
                            color: #243244;
                            font-size: 18px;
                            font-weight: 700;
                        }
                        Text { text: root.workspace_path; color: #314154; font-size: 12px; wrap: word-wrap; }
                        Text { text: root.project_summary; color: #5a6a7d; font-size: 12px; wrap: word-wrap; }
                    }

                    VerticalBox {
                        width: 280px;
                        spacing: 4px;
                        Text {
                            text: root.status_title;
                            color: #243244;
                            font-size: 12px;
                            font-weight: 700;
                            horizontal-alignment: right;
                        }
                        Text {
                            text: root.status_body;
                            color: #5a6a7d;
                            font-size: 11px;
                            wrap: word-wrap;
                            horizontal-alignment: right;
                        }
                        Text {
                            text: root.integration_summary + " | " + root.integration_detail;
                            color: #5a6a7d;
                            font-size: 11px;
                            wrap: word-wrap;
                            horizontal-alignment: right;
                        }
                    }
                }
            }

            HorizontalBox {
                spacing: 10px;

                SummaryCard {
                    horizontal-stretch: 1;
                    label: root.is_english ? "Total Files" : "鎬绘枃浠舵暟";
                    value: root.total_files;
                    detail: root.is_english ? "Tracked in current workspace" : "当前工作区已纳入统计";
                }

                SummaryCard {
                    horizontal-stretch: 1;
                    label: root.is_english ? "Pending Changes" : "待处理变更";
                    value: root.changed_files;
                    detail: root.is_english ? "Files differ from last saved version" : "与最近版本相比有差异";
                }

                SummaryCard {
                    horizontal-stretch: 1;
                    label: root.is_english ? "Saved Versions" : "历史版本";
                    value: root.total_versions;
                    detail: root.is_english ? "Available restore points" : "可用的恢复节点";
                }

                SummaryCard {
                    horizontal-stretch: 1;
                    label: root.is_english ? "Workspace Health" : "工作区指纹";
                    value: root.health_fingerprint;
                    detail: root.backup_label;
                }
            }

            HorizontalBox {
                spacing: 10px;
                height: 0px;
                visible: false;

                GroupFrame {
                    horizontal-stretch: 8;
                    VerticalBox {
                        padding: 8px;
                        spacing: 8px;
                        Rectangle {
                            height: 26px;
                            background: #edf2f7;
                            border-width: 1px;
                            border-color: #c7d0db;
                            Text { text: root.is_english ? "Project Information" : "项目信息"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                        }
                        Text { text: root.workspace_path; color: #233041; wrap: word-wrap; font-size: 13px; }
                        Text { text: root.project_summary; color: #4f6177; wrap: word-wrap; font-size: 12px; }
                        Text { text: root.is_english ? "Health Fingerprint: " + root.health_fingerprint : "健康指纹: " + root.health_fingerprint; color: #4f6177; font-size: 12px; }
                        Text { text: root.integration_summary + " | " + root.integration_detail; color: #4f6177; wrap: word-wrap; font-size: 12px; }
                    }
                }

                GroupFrame {
                    horizontal-stretch: 7;
                    VerticalBox {
                        padding: 8px;
                        spacing: 8px;
                        Rectangle {
                            height: 26px;
                            background: #edf2f7;
                            border-width: 1px;
                            border-color: #c7d0db;
                            Text { text: root.is_english ? "Settings" : "设置"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                        }
                        Text { text: root.language_label; color: #233041; wrap: word-wrap; font-size: 12px; }
                        Text { text: root.backup_label; color: #233041; wrap: word-wrap; font-size: 12px; }
                        Text {
                            text: root.is_english
                                ? "Open a workspace, then create versions and inspect differences here."
                                : "先打开工作区，然后在这里创建版本并查看差异。";
                            color: #4f6177;
                            wrap: word-wrap;
                            font-size: 12px;
                        }
                    }
                }
            }

            HorizontalBox {
                spacing: 10px;
                vertical-stretch: 1;

                GroupFrame {
                    horizontal-stretch: 9;
                    VerticalBox {
                        padding: 8px;
                        spacing: 8px;
                        Rectangle {
                            height: 26px;
                            background: #edf2f7;
                            border-width: 1px;
                            border-color: #c7d0db;
                            Text { text: root.is_english ? "File Changes" : "鏂囦欢鍙樻洿"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                        }
                        ListView {
                            for row in root.change_rows : Rectangle {
                                height: 64px;
                                background: transparent;
                                Rectangle {
                                    x: 0px;
                                    y: 3px;
                                    width: parent.width;
                                    height: parent.height - 6px;
                                    border-width: 1px;
                                    border-color: #d4dbe4;
                                    background: #ffffff;
                                    Text { text: row; x: 8px; y: 8px; width: parent.width - 16px; color: #233041; wrap: word-wrap; font-size: 12px; }
                                }
                            }
                        }
                        HorizontalBox {
                            Rectangle { horizontal-stretch: 1; }
                            ActionButton { label: root.is_english ? "Create Version" : "鎻愪氦鐗堟湰"; tapped => { root.create_version_requested(); } }
                        }
                    }
                }

                GroupFrame {
                    horizontal-stretch: 12;
                    VerticalBox {
                        padding: 8px;
                        spacing: 8px;
                        Rectangle {
                            height: 26px;
                            background: #edf2f7;
                            border-width: 1px;
                            border-color: #c7d0db;
                            Text { text: root.is_english ? "Version History" : "鐗堟湰鍘嗗彶"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                        }
                        ListView {
                            for row[i] in root.version_rows : Rectangle {
                                height: 76px;
                                background: transparent;
                                Rectangle {
                                    x: 0px;
                                    y: 3px;
                                    width: parent.width;
                                    height: parent.height - 6px;
                                    border-width: 1px;
                                    border-color: root.selected_version_index == i ? #6c87ad : #d4dbe4;
                                    background: root.selected_version_index == i ? #e5edf7 : #ffffff;
                                    Text { text: row; x: 8px; y: 9px; width: parent.width - 16px; color: #233041; wrap: word-wrap; font-size: 12px; }
                                }
                                TouchArea { clicked => { root.version_row_clicked(i); } }
                            }
                        }
                        HorizontalBox {
                            spacing: 6px;
                            ActionButton { label: root.is_english ? "View Details" : "鏌ョ湅璇︽儏"; tapped => { root.details_requested(); } }
                            ActionButton { label: root.is_english ? "Compare Versions" : "鐗堟湰瀵规瘮"; tapped => { root.compare_requested(); } }
                            ActionButton { label: root.is_english ? "Rollback Selected" : "鍥炴粴閫変腑鐗堟湰"; tapped => { root.rollback_requested(); } }
                            Rectangle { horizontal-stretch: 1; }
                            ActionButton { label: root.is_english ? "Refresh" : "鍒锋柊"; tapped => { root.refresh_requested(); } }
                        }
                    }
                }
            }

            Rectangle {
                height: 52px;
                background: #e7edf4;
                border-width: 1px;
                border-color: #b7c0cb;
                HorizontalBox {
                    padding: 8px;
                    spacing: 8px;
                    Text { text: root.status_title; color: #233041; font-size: 12px; font-weight: 700; vertical-alignment: center; }
                    Rectangle { width: 1px; background: #b7c0cb; }
                    Text { text: root.status_body; color: #4f6177; wrap: word-wrap; vertical-alignment: center; }
                    Rectangle { horizontal-stretch: 1; }
                    Text { text: root.is_english ? "Ready" : "灏辩华"; color: #6a798a; font-size: 11px; vertical-alignment: center; }
                }
            }
        }
    }

    if root.create_visible : Rectangle {
        background: #55000000;
        width: parent.width;
        height: parent.height;
        Rectangle {
            x: (parent.width - 520px) / 2;
            y: (parent.height - 290px) / 2;
            width: 520px;
            height: 290px;
            background: #f5f7fa;
            border-width: 1px;
            border-color: #9aa6b6;
            VerticalBox {
                padding: 14px;
                spacing: 10px;
                Text { text: root.is_english ? "Create Version" : "创建版本"; color: #243244; font-size: 20px; font-weight: 700; }
                Text {
                    text: root.is_english
                        ? "Add a short note so this version is easier to identify in history, compare, and rollback."
                        : "建议填写本次变更说明，方便后续在历史、对比和回滚时识别。";
                    color: #5a6a7d;
                    font-size: 12px;
                    wrap: word-wrap;
                }
                Rectangle { height: 1px; background: #d5dde7; }
                Text { text: root.is_english ? "Version Description" : "版本说明"; color: #243244; font-size: 12px; font-weight: 700; }
                TextEdit { text <=> root.create_description; height: 132px; }
                HorizontalBox {
                    spacing: 8px;
                    Rectangle { horizontal-stretch: 1; }
                    ActionButton { label: root.is_english ? "Cancel" : "取消"; tapped => { root.close_create_requested(); } }
                    ActionButton { label: root.is_english ? "Submit" : "提交"; primary: true; tapped => { root.submit_create_requested(); } }
                }
            }
        }
    }

    if root.details_visible : Rectangle {
        background: #55000000;
        width: parent.width;
        height: parent.height;
        Rectangle {
            x: 24px;
            y: 20px;
            width: parent.width - 48px;
            height: parent.height - 40px;
            background: #f5f7fa;
            border-width: 1px;
            border-color: #9aa6b6;
            VerticalBox {
                padding: 12px;
                spacing: 6px;
                HorizontalBox {
                    spacing: 8px;
                    Text { text: root.details_title; color: #243244; font-size: 20px; font-weight: 700; }
                    Rectangle { horizontal-stretch: 1; }
                    if !root.preview_is_text : ActionButton { label: root.is_english ? "Open Externally" : "使用系统打开"; tapped => { root.open_selected_file_requested(); } }
                    ActionButton { label: root.is_english ? "Close" : "关闭"; tapped => { root.close_details_requested(); } }
                }
                Text { text: root.details_meta; color: #4f6177; wrap: word-wrap; font-size: 12px; }
                Text { text: root.details_stats; color: #4f6177; wrap: word-wrap; font-size: 12px; }
                Rectangle {
                    height: 34px;
                    background: #edf2f7;
                    border-width: 1px;
                    border-color: #c7d0db;
                    HorizontalBox {
                        padding: 8px;
                        Text { text: root.preview_note; color: #415266; font-size: 11px; vertical-alignment: center; }
                    }
                }
                HorizontalBox {
                    spacing: 10px;
                    GroupFrame {
                        horizontal-stretch: 7;
                        VerticalBox {
                            padding: 8px;
                            spacing: 8px;
                            Rectangle {
                                height: 26px;
                                background: #edf2f7;
                                border-width: 1px;
                                border-color: #c7d0db;
                                Text { text: root.is_english ? "Files" : "文件列表"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                            }
                            ListView {
                                for row[i] in root.detail_rows : Rectangle {
                                    height: 60px;
                                    background: transparent;
                                    Rectangle {
                                        x: 0px;
                                        y: 3px;
                                        width: parent.width;
                                        height: parent.height - 6px;
                                        border-width: 1px;
                                        border-color: root.selected_detail_index == i ? #6c87ad : #d4dbe4;
                                        background: root.selected_detail_index == i ? #e5edf7 : #ffffff;
                                        Text { text: row; x: 8px; y: 8px; width: parent.width - 16px; color: #233041; wrap: word-wrap; font-size: 12px; }
                                    }
                                    TouchArea { clicked => { root.detail_file_clicked(i); } }
                                }
                            }
                        }
                    }
                    GroupFrame {
                        horizontal-stretch: 13;
                        VerticalBox {
                            padding: 8px;
                            spacing: 8px;
                            Rectangle {
                                height: 26px;
                                background: #edf2f7;
                                border-width: 1px;
                                border-color: #c7d0db;
                                Text { text: root.is_english ? "Text Preview" : "文本预览"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                            }
                            HorizontalBox {
                                spacing: 8px;
                                GroupFrame {
                                    horizontal-stretch: 1;
                                    VerticalBox {
                                        padding: 8px;
                                        spacing: 6px;
                                        Rectangle {
                                            height: 24px;
                                            background: #edf2f7;
                                            border-width: 1px;
                                            border-color: #c7d0db;
                                            Text { text: root.preview_left_label; x: 8px; y: 4px; color: #243244; font-size: 13px; font-weight: 700; }
                                        }
                                        ListView {
                                            for line in root.preview_left_lines : Rectangle {
                                                height: 24px;
                                                border-width: 1px;
                                                border-color: #edf1f5;
                                                background: #ffffff;
                                                Text { text: line.text; x: 6px; y: 4px; width: parent.width - 12px; color: line.highlight ? #c43b3b : #233041; font-size: 12px; }
                                            }
                                        }
                                    }
                                }
                                GroupFrame {
                                    horizontal-stretch: 1;
                                    VerticalBox {
                                        padding: 8px;
                                        spacing: 6px;
                                        Rectangle {
                                            height: 24px;
                                            background: #edf2f7;
                                            border-width: 1px;
                                            border-color: #c7d0db;
                                            Text { text: root.preview_right_label; x: 8px; y: 4px; color: #243244; font-size: 13px; font-weight: 700; }
                                        }
                                        ListView {
                                            for line in root.preview_right_lines : Rectangle {
                                                height: 24px;
                                                border-width: 1px;
                                                border-color: #edf1f5;
                                                background: #ffffff;
                                                Text { text: line.text; x: 6px; y: 4px; width: parent.width - 12px; color: line.highlight ? #c43b3b : #233041; font-size: 12px; }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if root.compare_visible : Rectangle {
        background: #55000000;
        width: parent.width;
        height: parent.height;
        Rectangle {
            x: 44px;
            y: 34px;
            width: parent.width - 88px;
            height: parent.height - 68px;
            background: #f5f7fa;
            border-width: 1px;
            border-color: #9aa6b6;
            VerticalBox {
                padding: 12px;
                spacing: 8px;
                HorizontalBox {
                    spacing: 8px;
                    Text { text: root.compare_title; color: #243244; font-size: 20px; font-weight: 700; }
                    Rectangle { horizontal-stretch: 1; }
                    ActionButton { label: root.is_english ? "Close" : "关闭"; tapped => { root.close_compare_requested(); } }
                }
                Rectangle {
                    height: 36px;
                    background: #edf2f7;
                    border-width: 1px;
                    border-color: #c7d0db;
                    HorizontalBox {
                        padding: 8px;
                        Text { text: root.compare_summary; color: #415266; font-size: 12px; vertical-alignment: center; }
                    }
                }
                GroupFrame {
                    height: 108px;
                    VerticalBox {
                        padding: 8px;
                        spacing: 6px;
                        Rectangle {
                            height: 26px;
                            background: #edf2f7;
                            border-width: 1px;
                            border-color: #c7d0db;
                            Text { text: root.is_english ? "Compare Selection" : "对比选择"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                        }
                        HorizontalBox {
                            spacing: 10px;
                            VerticalBox {
                                horizontal-stretch: 1;
                                spacing: 4px;
                                Text { text: root.is_english ? "Base Version" : "基准版本"; color: #233041; font-size: 12px; }
                                ComboBox { model: root.compare_version_options; current-index <=> root.compare_left_index; height: 32px; }
                            }
                            VerticalBox {
                                horizontal-stretch: 1;
                                spacing: 4px;
                                Text { text: root.is_english ? "Target Version" : "目标版本"; color: #233041; font-size: 12px; }
                                ComboBox { model: root.compare_version_options; current-index <=> root.compare_right_index; height: 32px; }
                            }
                            VerticalBox {
                                width: 180px;
                                spacing: 4px;
                                Text { text: root.is_english ? "Action" : "操作"; color: #233041; font-size: 12px; }
                    ActionButton { label: root.is_english ? "Run Compare" : "开始对比"; primary: true; tapped => { root.perform_compare_requested(); } }
                            }
                        }
                    }
                }
                GroupFrame {
                    VerticalBox {
                        padding: 8px;
                        spacing: 8px;
                        Rectangle {
                            height: 26px;
                            background: #edf2f7;
                            border-width: 1px;
                            border-color: #c7d0db;
                            Text { text: root.is_english ? "Compare Result" : "对比结果"; x: 8px; y: 4px; color: #243244; font-size: 14px; font-weight: 700; }
                        }
                        ListView {
                            for row in root.compare_rows : Rectangle {
                                height: 60px;
                                background: transparent;
                                Rectangle {
                                    x: 0px;
                                    y: 3px;
                                    width: parent.width;
                                    height: parent.height - 6px;
                                    border-width: 1px;
                                    border-color: #d4dbe4;
                                    background: #ffffff;
                                    Text { text: row; x: 8px; y: 8px; width: parent.width - 16px; color: #233041; wrap: word-wrap; font-size: 12px; }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if root.settings_visible : Rectangle {
        background: #55000000;
        width: parent.width;
        height: parent.height;
        Rectangle {
            x: (parent.width - 520px) / 2;
            y: (parent.height - 280px) / 2;
            width: 520px;
            height: 280px;
            background: #f5f7fa;
            border-width: 1px;
            border-color: #9aa6b6;
            VerticalBox {
                padding: 14px;
                spacing: 10px;
                Text { text: root.settings_title; color: #243244; font-size: 20px; font-weight: 700; }
                Text {
                    text: root.is_english
                        ? "Update display and rollback behavior here. Each option shows its current state."
                        : "在这里调整显示和回滚行为，每一项都会直接展示当前状态。";
                    color: #5a6a7d;
                    font-size: 12px;
                    wrap: word-wrap;
                }
                Rectangle { height: 1px; background: #d5dde7; }
                SettingRow {
                    title: root.is_english ? "Language" : "语言";
                    description: root.is_english ? "Switch the interface language for the full application." : "切换整个应用界面的显示语言。";
                    value: root.language_label;
                    tapped => { root.toggle_language_requested(); }
                }
                SettingRow {
                    title: root.is_english ? "Backup Before Rollback" : "回滚前备份";
                    description: root.is_english ? "Create a backup of the current workspace before restoring a saved version." : "在恢复历史版本前，先备份当前工作区。";
                    value: root.backup_label;
                    tapped => { root.toggle_backup_requested(); }
                }
                HorizontalBox {
                    spacing: 8px;
                    Rectangle { horizontal-stretch: 1; }
                    ActionButton { label: root.is_english ? "Close" : "关闭"; tapped => { root.close_settings_requested(); } }
                }
            }
        }
    }

    if root.rollback_visible : Rectangle {
        background: #55000000;
        width: parent.width;
        height: parent.height;
        Rectangle {
            x: (parent.width - 520px) / 2;
            y: (parent.height - 240px) / 2;
            width: 520px;
            height: 240px;
            background: #f5f7fa;
            border-width: 1px;
            border-color: #9aa6b6;
            VerticalBox {
                padding: 14px;
                spacing: 10px;
                Text { text: root.rollback_title; color: #243244; font-size: 20px; font-weight: 700; }
                Rectangle {
                    background: #f9e5e5;
                    border-width: 1px;
                    border-color: #e2b8b8;
                    height: 56px;
                    VerticalBox {
                        padding: 8px;
                        spacing: 2px;
                        Text { text: root.is_english ? "This will overwrite the current workspace with the selected version." : "此操作会用所选版本覆盖当前工作区。"; color: #7c2222; font-size: 12px; font-weight: 700; }
                        Text { text: root.is_english ? "Review the backup setting below before confirming." : "确认前请留意下方备份设置说明。"; color: #934040; font-size: 11px; }
                    }
                }
                Text { text: root.rollback_body; color: #4f6177; wrap: word-wrap; font-size: 12px; }
                HorizontalBox {
                    spacing: 8px;
                    Rectangle { horizontal-stretch: 1; }
                    ActionButton { label: root.is_english ? "Cancel" : "取消"; tapped => { root.close_rollback_requested(); } }
                    ActionButton { label: root.is_english ? "Confirm" : "确认"; danger: true; tapped => { root.rollback_confirmed(); } }
                }
            }
        }
    }
}
}

#[derive(Clone)]
struct UiState {
    dashboard: WorkspaceData,
    settings: AppSettings,
    selected_version_index: usize,
    create_description: String,
    details: Option<VersionDetails>,
    preview: Option<VersionFilePreview>,
    selected_detail_index: usize,
    compare: Option<VersionDiffResult>,
    compare_left_index: usize,
    compare_right_index: usize,
}

impl Default for UiState {
    fn default() -> Self {
        Self {
            dashboard: WorkspaceData::empty(String::new()),
            settings: AppSettings::default(),
            selected_version_index: 0,
            create_description: String::new(),
            details: None,
            preview: None,
            selected_detail_index: 0,
            compare: None,
            compare_left_index: 0,
            compare_right_index: 0,
        }
    }
}

fn main() -> Result<()> {
    let app = AppWindow::new()?;
    constrain_window_height(&app);
    let engine = Rc::new(RefCell::new(Engine::bootstrap()?));
    let state = Rc::new(RefCell::new(UiState::default()));
    refresh_dashboard(&app, &engine, &state, "ready")?;
    wire_callbacks(&app, engine, state);
    app.run()?;
    Ok(())
}

fn wire_callbacks(app: &AppWindow, engine: Rc<RefCell<Engine>>, state: Rc<RefCell<UiState>>) {
    let weak = app.as_weak();

    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_open_workspace_requested(move || {
            if let Some(path) = rfd::FileDialog::new()
                .set_title("Select VerMan workspace")
                .pick_folder()
            {
                if let Some(app) = weak.upgrade() {
                    match engine.borrow_mut().open_workspace(path) {
                        Ok(dashboard) => {
                            let settings = engine.borrow().settings().unwrap_or_default();
                            let mut s = state.borrow_mut();
                            s.dashboard = dashboard;
                            s.settings = settings;
                            s.selected_version_index = 0;
                            s.details = None;
                            s.preview = None;
                            s.compare = None;
                            app.set_create_visible(false);
                            app.set_details_visible(false);
                            app.set_compare_visible(false);
                            app.set_settings_visible(false);
                            app.set_rollback_visible(false);
                            apply_ui(&app, &s, "workspace_opened", "");
                        }
                        Err(error) => set_status(
                            &app,
                            is_en(&state.borrow().settings),
                            "error",
                            &error.to_string(),
                        ),
                    }
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_open_selected_file_requested(move || {
            if let Some(app) = weak.upgrade() {
                let state_ref = state.borrow();
                let Some(version_id) = selected_version_id(&state_ref) else {
                    return;
                };
                let selected_index = state_ref.selected_detail_index;
                let relative_path = state_ref
                    .details
                    .as_ref()
                    .and_then(|d| d.files.get(selected_index))
                    .map(|f| f.relative_path.clone());
                let is_english = is_en(&state_ref.settings);
                drop(state_ref);
                if let Some(path) = relative_path {
                    if let Err(error) = engine
                        .borrow()
                        .open_version_file_external(version_id, &path)
                    {
                        set_status(&app, is_english, "error", &error.to_string());
                    }
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_refresh_requested(move || {
            if let Some(app) = weak.upgrade() {
                let _ =
                    refresh_dashboard(&app, &engine, &state, "refresh_complete").map_err(|error| {
                        set_status(
                            &app,
                            is_en(&state.borrow().settings),
                            "error",
                            &error.to_string(),
                        )
                    });
            }
        });
    }
    {
        let weak = weak.clone();
        let state = state.clone();
        app.on_create_version_requested(move || {
            if let Some(app) = weak.upgrade() {
                let mut s = state.borrow_mut();
                s.create_description.clear();
                app.set_create_visible(true);
                apply_ui(&app, &s, "ready", "");
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_submit_create_requested(move || {
            if let Some(app) = weak.upgrade() {
                let description = app.get_create_description().to_string();
                match engine.borrow_mut().create_version(&description) {
                    Ok(dashboard) => {
                        let mut s = state.borrow_mut();
                        s.dashboard = dashboard;
                        s.selected_version_index = 0;
                        s.create_description.clear();
                        s.details = None;
                        s.preview = None;
                        s.compare = None;
                        app.set_create_visible(false);
                        apply_ui(&app, &s, "version_created", "");
                    }
                    Err(error) => set_status(
                        &app,
                        is_en(&state.borrow().settings),
                        "error",
                        &error.to_string(),
                    ),
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let state = state.clone();
        app.on_version_row_clicked(move |index| {
            if let Some(app) = weak.upgrade() {
                let mut s = state.borrow_mut();
                s.selected_version_index = index.max(0) as usize;
                apply_ui(&app, &s, "ready", "");
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_details_requested(move || {
            if let Some(app) = weak.upgrade() {
                let Some(version_id) = selected_version_id(&state.borrow()) else {
                    set_status(&app, is_en(&state.borrow().settings), "need_version", "");
                    return;
                };
                match engine.borrow().version_details(version_id) {
                    Ok(details) => {
                        let preview = details.files.first().and_then(|file| {
                            engine
                                .borrow()
                                .version_file_preview(version_id, &file.relative_path)
                                .ok()
                        });
                        let mut s = state.borrow_mut();
                        s.details = Some(details);
                        s.preview = preview;
                        s.selected_detail_index = 0;
                        app.set_details_visible(true);
                        apply_ui(&app, &s, "details_loaded", "");
                    }
                    Err(error) => set_status(
                        &app,
                        is_en(&state.borrow().settings),
                        "error",
                        &error.to_string(),
                    ),
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_detail_file_clicked(move |index| {
            if let Some(app) = weak.upgrade() {
                let Some(version_id) = selected_version_id(&state.borrow()) else {
                    return;
                };
                let relative_path = state
                    .borrow()
                    .details
                    .as_ref()
                    .and_then(|d| d.files.get(index.max(0) as usize))
                    .map(|f| f.relative_path.clone());
                if let Some(path) = relative_path {
                    match engine.borrow().version_file_preview(version_id, &path) {
                        Ok(preview) => {
                            let mut s = state.borrow_mut();
                            s.preview = Some(preview);
                            s.selected_detail_index = index.max(0) as usize;
                            apply_ui(&app, &s, "details_loaded", "");
                        }
                        Err(error) => set_status(
                            &app,
                            is_en(&state.borrow().settings),
                            "error",
                            &error.to_string(),
                        ),
                    }
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let state = state.clone();
        app.on_compare_requested(move || {
            if let Some(app) = weak.upgrade() {
                let s_ref = state.borrow();
                let Some(right_index) = s_ref
                    .dashboard
                    .versions
                    .get(s_ref.selected_version_index)
                    .map(|_| s_ref.selected_version_index)
                else {
                    set_status(&app, is_en(&s_ref.settings), "need_version", "");
                    return;
                };
                let left_index = if s_ref.dashboard.versions.len() > 1 {
                    if right_index + 1 < s_ref.dashboard.versions.len() {
                        right_index + 1
                    } else {
                        0
                    }
                } else {
                    right_index
                };
                drop(s_ref);
                let mut s = state.borrow_mut();
                s.compare_left_index = left_index;
                s.compare_right_index = right_index;
                s.compare = None;
                app.set_compare_visible(true);
                apply_ui(&app, &s, "ready", "");
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_perform_compare_requested(move || {
            if let Some(app) = weak.upgrade() {
                let left_index = app.get_compare_left_index().max(0) as usize;
                let right_index = app.get_compare_right_index().max(0) as usize;
                {
                    let mut s = state.borrow_mut();
                    s.compare_left_index = left_index;
                    s.compare_right_index = right_index;
                }
                if left_index == right_index {
                    let en = is_en(&state.borrow().settings);
                    set_status(
                        &app,
                        en,
                        "error",
                        tr(
                            en,
                            "请选择两个不同的版本进行对比。",
                            "Choose two different versions to compare.",
                        ),
                    );
                    return;
                }
                let s_ref = state.borrow();
                let Some(left) = s_ref.dashboard.versions.get(left_index).map(|v| v.id) else {
                    set_status(&app, is_en(&s_ref.settings), "need_compare_pair", "");
                    return;
                };
                let Some(right) = s_ref.dashboard.versions.get(right_index).map(|v| v.id) else {
                    set_status(&app, is_en(&s_ref.settings), "need_compare_pair", "");
                    return;
                };
                drop(s_ref);
                match engine.borrow().compare_versions(left, right) {
                    Ok(compare) => {
                        let mut s = state.borrow_mut();
                        s.compare = Some(compare);
                        apply_ui(&app, &s, "compare_loaded", "");
                    }
                    Err(error) => set_status(
                        &app,
                        is_en(&state.borrow().settings),
                        "error",
                        &error.to_string(),
                    ),
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let state = state.clone();
        app.on_rollback_requested(move || {
            if let Some(app) = weak.upgrade() {
                if selected_version_id(&state.borrow()).is_none() {
                    set_status(&app, is_en(&state.borrow().settings), "need_version", "");
                } else {
                    app.set_rollback_visible(true);
                    apply_ui(&app, &state.borrow(), "rollback_ready", "");
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_rollback_confirmed(move || {
            if let Some(app) = weak.upgrade() {
                let Some(version_id) = selected_version_id(&state.borrow()) else {
                    return;
                };
                let backup = state.borrow().settings.backup_before_restore;
                match engine.borrow_mut().rollback_to_version(version_id, backup) {
                    Ok(dashboard) => {
                        let mut s = state.borrow_mut();
                        s.dashboard = dashboard;
                        s.details = None;
                        s.preview = None;
                        s.compare = None;
                        app.set_rollback_visible(false);
                        apply_ui(&app, &s, "rollback_done", "");
                    }
                    Err(error) => set_status(
                        &app,
                        is_en(&state.borrow().settings),
                        "error",
                        &error.to_string(),
                    ),
                }
            }
        });
    }
    {
        let weak = weak.clone();
        let state = state.clone();
        app.on_settings_requested(move || {
            if let Some(app) = weak.upgrade() {
                app.set_settings_visible(true);
                apply_ui(&app, &state.borrow(), "ready", "");
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_toggle_language_requested(move || {
            if let Some(app) = weak.upgrade() {
                let mut s = state.borrow_mut();
                s.settings.language = if s.settings.language == "en" {
                    "zh".into()
                } else {
                    "en".into()
                };
                if let Err(error) = engine.borrow().save_settings(&s.settings) {
                    set_status(&app, is_en(&s.settings), "error", &error.to_string());
                    return;
                }
                apply_ui(&app, &s, "settings_saved", "");
            }
        });
    }
    {
        let weak = weak.clone();
        let engine = engine.clone();
        let state = state.clone();
        app.on_toggle_backup_requested(move || {
            if let Some(app) = weak.upgrade() {
                let mut s = state.borrow_mut();
                s.settings.backup_before_restore = !s.settings.backup_before_restore;
                if let Err(error) = engine.borrow().save_settings(&s.settings) {
                    set_status(&app, is_en(&s.settings), "error", &error.to_string());
                    return;
                }
                apply_ui(&app, &s, "settings_saved", "");
            }
        });
    }
    {
        let weak = weak.clone();
        app.on_close_create_requested(move || {
            if let Some(app) = weak.upgrade() {
                app.set_create_visible(false);
            }
        });
    }
    {
        let weak = weak.clone();
        app.on_close_details_requested(move || {
            if let Some(app) = weak.upgrade() {
                app.set_details_visible(false);
            }
        });
    }
    {
        let weak = weak.clone();
        app.on_close_compare_requested(move || {
            if let Some(app) = weak.upgrade() {
                app.set_compare_visible(false);
            }
        });
    }
    {
        let weak = weak.clone();
        app.on_close_settings_requested(move || {
            if let Some(app) = weak.upgrade() {
                app.set_settings_visible(false);
            }
        });
    }
    {
        let weak = weak.clone();
        app.on_close_rollback_requested(move || {
            if let Some(app) = weak.upgrade() {
                app.set_rollback_visible(false);
            }
        });
    }
}

fn refresh_dashboard(
    app: &AppWindow,
    engine: &Rc<RefCell<Engine>>,
    state: &Rc<RefCell<UiState>>,
    status_key: &str,
) -> Result<()> {
    let dashboard = engine.borrow_mut().dashboard()?;
    let settings = engine.borrow().settings().unwrap_or_default();
    let mut s = state.borrow_mut();
    s.dashboard = dashboard;
    s.settings = settings;
    s.details = None;
    s.preview = None;
    s.compare = None;
    s.selected_version_index = s
        .selected_version_index
        .min(s.dashboard.versions.len().saturating_sub(1));
    apply_ui(app, &s, status_key, "");
    Ok(())
}

fn apply_ui(app: &AppWindow, state: &UiState, status_key: &str, error: &str) {
    let is_english = is_en(&state.settings);
    let dashboard = &state.dashboard;

    app.set_is_english(is_english);
    app.set_workspace_path(if dashboard.workspace_path.is_empty() {
        tr(is_english, "未打开工作区", "No workspace opened").into()
    } else {
        dashboard.workspace_path.clone().into()
    });
    app.set_project_summary(
        format!(
            "{} {}  {} {}  {} {}  {} {}",
            tr(is_english, "文件数", "Files"),
            dashboard.total_files,
            tr(is_english, "版本数", "Versions"),
            dashboard.total_versions,
            tr(is_english, "变更数", "Changes"),
            dashboard.changed_files,
            tr(is_english, "忽略规则", "Ignore Rules"),
            dashboard
                .ignore_rules
                .lines()
                .filter(|line| !line.trim().is_empty() && !line.trim().starts_with('#'))
                .count()
        )
        .into(),
    );
    app.set_total_files(dashboard.total_files.to_string().into());
    app.set_total_versions(dashboard.total_versions.to_string().into());
    app.set_changed_files(dashboard.changed_files.to_string().into());
    app.set_ignore_rule_count(
        dashboard
            .ignore_rules
            .lines()
            .filter(|line| !line.trim().is_empty() && !line.trim().starts_with('#'))
            .count()
            .to_string()
            .into(),
    );
    app.set_health_fingerprint(compute_health(dashboard).into());

    let ctx = explorer_integration_status();
    app.set_integration_summary(
        if ctx.installed {
            tr(
                is_english,
                "资源管理器集成已安装",
                "Explorer integration installed",
            )
        } else if ctx.supported {
            tr(
                is_english,
                "资源管理器集成未安装",
                "Explorer integration not installed",
            )
        } else {
            tr(
                is_english,
                "资源管理器集成不可用",
                "Explorer integration unavailable",
            )
        }
        .into(),
    );
    app.set_integration_detail(ctx.detail.into());
    app.set_language_label(
        if is_english {
            "Language: English / 中文"
        } else {
            "语言: 中文 / English"
        }
        .into(),
    );
    app.set_backup_label(
        if state.settings.backup_before_restore {
            tr(
                is_english,
                "回滚前自动备份: 已开启",
                "Backup before rollback: On",
            )
        } else {
            tr(
                is_english,
                "回滚前自动备份: 已关闭",
                "Backup before rollback: Off",
            )
        }
        .into(),
    );

    app.set_selected_version_index(state.selected_version_index as i32);
    app.set_create_description(state.create_description.clone().into());
    app.set_change_rows(ModelRc::new(VecModel::from(build_change_rows(
        dashboard, is_english,
    ))));
    app.set_version_rows(ModelRc::new(VecModel::from(build_version_rows(
        dashboard, is_english,
    ))));

    let (title, body) = status_message(is_english, status_key, error);
    app.set_status_title(title.into());
    app.set_status_body(body.into());

    app.set_details_title(
        state
            .details
            .as_ref()
            .map(|d| {
                format!(
                    "{} | {}",
                    tr(is_english, "版本详情", "Version Details"),
                    d.version.version_number
                )
            })
            .unwrap_or_default()
            .into(),
    );
    app.set_details_meta(
        state
            .details
            .as_ref()
            .map(|d| {
                format!(
                    "{} | {} | {}",
                    d.version.description,
                    d.version.created_at.format("%Y-%m-%d %H:%M:%S"),
                    d.previous_version_label.clone().unwrap_or_else(|| tr(
                        is_english,
                        "无上一个版本",
                        "No previous version"
                    )
                    .to_string())
                )
            })
            .unwrap_or_default()
            .into(),
    );
    app.set_details_stats(
        state
            .details
            .as_ref()
            .map(|d| {
                format!(
                    "{} {}  {} {}  {} {}",
                    tr(is_english, "新增", "Added"),
                    d.stats.add_count,
                    tr(is_english, "修改", "Modified"),
                    d.stats.modify_count,
                    tr(is_english, "删除", "Deleted"),
                    d.stats.delete_count
                )
            })
            .unwrap_or_default()
            .into(),
    );
    app.set_detail_rows(ModelRc::new(VecModel::from(build_detail_rows(
        state, is_english,
    ))));
    app.set_selected_detail_index(state.selected_detail_index as i32);

    let (left_label, right_label, left_lines, right_lines, note, is_text) =
        build_preview_payload(state, is_english);
    app.set_preview_left_label(left_label.into());
    app.set_preview_right_label(right_label.into());
    app.set_preview_is_text(is_text);
    app.set_preview_left_lines(ModelRc::new(VecModel::from(left_lines)));
    app.set_preview_right_lines(ModelRc::new(VecModel::from(right_lines)));
    app.set_preview_note(note.into());

    app.set_compare_title(
        state
            .compare
            .as_ref()
            .map(|c| {
                format!(
                    "{} | {} -> {}",
                    tr(is_english, "版本对比", "Version Compare"),
                    c.left_version_label,
                    c.right_version_label
                )
            })
            .unwrap_or_else(|| tr(is_english, "版本对比", "Version Compare").to_string())
            .into(),
    );
    app.set_compare_summary(
        state
            .compare
            .as_ref()
            .map(|c| {
                format!(
                    "{} {}  {} {}  {} {}",
                    tr(is_english, "新增", "Added"),
                    c.added,
                    tr(is_english, "修改", "Modified"),
                    c.modified,
                    tr(is_english, "删除", "Deleted"),
                    c.deleted
                )
            })
            .unwrap_or_else(|| {
                tr(
                    is_english,
                    "手动选择两个版本后开始对比。",
                    "Choose two versions and run compare.",
                )
                .to_string()
            })
            .into(),
    );
    app.set_compare_version_options(ModelRc::new(VecModel::from(build_compare_options(
        dashboard, is_english,
    ))));
    app.set_compare_left_index(state.compare_left_index as i32);
    app.set_compare_right_index(state.compare_right_index as i32);
    app.set_compare_rows(ModelRc::new(VecModel::from(build_compare_rows(
        state, is_english,
    ))));

    app.set_settings_title(tr(is_english, "设置", "Settings").into());
    app.set_settings_body(
        tr(
            is_english,
            "这里可以切换中英文，并决定回滚前是否自动备份当前工作区。",
            "Switch language here and decide whether rollback should create a backup first.",
        )
        .into(),
    );
    app.set_rollback_title(tr(is_english, "确认回滚", "Confirm Rollback").into());
    app.set_rollback_body(
        if state.settings.backup_before_restore {
            tr(
                is_english,
                "将回滚到当前选中的版本，并在操作前先备份当前工作区。",
                "The workspace will roll back to the selected version and create a backup first.",
            )
        } else {
            tr(
                is_english,
                "将直接回滚到当前选中的版本，不额外创建备份。",
                "The workspace will roll back directly to the selected version without an extra backup.",
            )
        }
        .into(),
    );
}

fn build_change_rows(d: &WorkspaceData, en: bool) -> Vec<SharedString> {
    let mut rows = d
        .changes
        .iter()
        .map(|e| {
            SharedString::from(format!(
                "[{}] {} | {}",
                status_label(&e.status, en),
                e.relative_path,
                format_size(e.size)
            ))
        })
        .collect::<Vec<_>>();
    if rows.is_empty() {
        rows.push(SharedString::from(if en {
            "No current file changes."
        } else {
            "当前没有检测到文件变更。"
        }));
    }
    rows
}

fn build_version_rows(d: &WorkspaceData, en: bool) -> Vec<SharedString> {
    let mut rows = d
        .versions
        .iter()
        .map(|v| {
            SharedString::from(format!(
                "{} | {} | {} | {}",
                v.version_number,
                if v.description.trim().is_empty() {
                    tr(en, "无描述", "No description").to_string()
                } else {
                    v.description.clone()
                },
                if en {
                    format!("{} files", v.change_count)
                } else {
                    format!("{} 个文件", v.change_count)
                },
                v.created_at.format("%Y-%m-%d %H:%M:%S")
            ))
        })
        .collect::<Vec<_>>();
    if rows.is_empty() {
        rows.push(SharedString::from(if en {
            "No versions yet. Use Create Version to save the current workspace."
        } else {
            "还没有版本，点击 \"提交版本\" 保存当前工作区。"
        }));
    }
    rows
}

fn build_compare_options(d: &WorkspaceData, en: bool) -> Vec<SharedString> {
    let mut rows = d
        .versions
        .iter()
        .map(|v| {
            SharedString::from(format!(
                "{} | {} | {}",
                v.version_number,
                if v.description.trim().is_empty() {
                    tr(en, "无描述", "No description").to_string()
                } else {
                    v.description.clone()
                },
                if en {
                    format!("{} files", v.change_count)
                } else {
                    format!("{} 个文件", v.change_count)
                }
            ))
        })
        .collect::<Vec<_>>();
    if rows.is_empty() {
        rows.push(SharedString::from(if en {
            "No versions available"
        } else {
            "没有可选版本"
        }));
    }
    rows
}

fn build_detail_rows(state: &UiState, en: bool) -> Vec<SharedString> {
    state
        .details
        .as_ref()
        .map(|d| {
            let mut rows = d
                .files
                .iter()
                .map(|f| {
                    SharedString::from(format!(
                        "[{}] {} | {}",
                        status_label(&f.status, en),
                        f.relative_path,
                        format_size(f.size)
                    ))
                })
                .collect::<Vec<_>>();
            if rows.is_empty() {
                rows.push(SharedString::from(if en {
                    "This version has no changed files."
                } else {
                    "该版本没有变更文件。"
                }));
            }
            rows
        })
        .unwrap_or_else(|| {
            vec![SharedString::from(if en {
                "No details loaded."
            } else {
                "尚未加载版本详情。"
            })]
        })
}

fn build_preview_data(
    state: &UiState,
    en: bool,
) -> (String, String, Vec<SharedString>, Vec<SharedString>, String) {
    let Some(preview) = &state.preview else {
        return (
            tr(en, "上一版本", "Previous").into(),
            tr(en, "当前版本", "Current").into(),
            vec![SharedString::from(tr(en, "(空)", "(empty)"))],
            vec![SharedString::from(tr(en, "(空)", "(empty)"))],
            tr(
                en,
                "从左侧文件列表中选择一个文件进行预览。",
                "Select a file from the list to preview.",
            )
            .into(),
        );
    };

    let note = if preview.is_text {
        preview
            .note
            .clone()
            .unwrap_or_else(|| preview.relative_path.clone())
    } else {
        preview.note.clone().unwrap_or_else(|| {
            tr(
                en,
                "该文件是二进制内容，当前仅显示文本预览占位。",
                "This file looks binary, so only text preview placeholders are shown.",
            )
            .to_string()
        })
    };

    (
        preview.left_label.clone(),
        preview.right_label.clone(),
        text_to_lines(preview.left_text.as_deref(), en),
        text_to_lines(preview.right_text.as_deref(), en),
        note,
    )
}

fn text_to_lines(text: Option<&str>, en: bool) -> Vec<SharedString> {
    let mut lines = text
        .unwrap_or("")
        .lines()
        .take(800)
        .map(|line| SharedString::from(line.to_string()))
        .collect::<Vec<_>>();
    if lines.is_empty() {
        lines.push(SharedString::from(tr(en, "(空)", "(empty)")));
    }
    lines
}

fn build_preview_payload(
    state: &UiState,
    en: bool,
) -> (
    String,
    String,
    Vec<PreviewLine>,
    Vec<PreviewLine>,
    String,
    bool,
) {
    let Some(preview) = &state.preview else {
        return (
            tr(en, "上一版本", "Previous").into(),
            tr(en, "当前版本", "Current").into(),
            vec![PreviewLine {
                text: tr(en, "(空)", "(empty)").into(),
                highlight: false,
            }],
            vec![PreviewLine {
                text: tr(en, "(空)", "(empty)").into(),
                highlight: false,
            }],
            tr(
                en,
                "从左侧文件列表中选择一个文件进行预览。",
                "Select a file from the list to preview.",
            )
            .into(),
            true,
        );
    };

    let note = if preview.is_text {
        preview
            .note
            .clone()
            .unwrap_or_else(|| preview.relative_path.clone())
    } else {
        preview.note.clone().unwrap_or_else(|| {
            tr(
                en,
                "该文件是二进制内容，可通过系统程序打开查看。",
                "This file looks binary. Use the external open action to inspect it.",
            )
            .to_string()
        })
    };

    (
        preview.left_label.clone(),
        preview.right_label.clone(),
        diff_preview_lines(
            preview.left_text.as_deref(),
            preview.right_text.as_deref(),
            true,
            en,
        ),
        diff_preview_lines(
            preview.left_text.as_deref(),
            preview.right_text.as_deref(),
            false,
            en,
        ),
        note,
        preview.is_text,
    )
}

fn diff_preview_lines(
    left: Option<&str>,
    right: Option<&str>,
    use_left: bool,
    en: bool,
) -> Vec<PreviewLine> {
    let left_lines = left
        .unwrap_or("")
        .lines()
        .take(800)
        .map(str::to_string)
        .collect::<Vec<_>>();
    let right_lines = right
        .unwrap_or("")
        .lines()
        .take(800)
        .map(str::to_string)
        .collect::<Vec<_>>();
    let max_len = left_lines.len().max(right_lines.len());
    let mut rows = Vec::new();

    for index in 0..max_len {
        let left_line = left_lines.get(index).cloned().unwrap_or_default();
        let right_line = right_lines.get(index).cloned().unwrap_or_default();
        let text = if use_left {
            left_line.clone()
        } else {
            right_line.clone()
        };
        rows.push(PreviewLine {
            text: if text.is_empty() {
                "".into()
            } else {
                text.into()
            },
            highlight: left_line != right_line,
        });
    }

    if rows.is_empty() {
        rows.push(PreviewLine {
            text: tr(en, "(空)", "(empty)").into(),
            highlight: false,
        });
    }

    rows
}

fn build_compare_rows(state: &UiState, en: bool) -> Vec<SharedString> {
    state
        .compare
        .as_ref()
        .map(|c| {
            let mut rows = c
                .entries
                .iter()
                .map(|e| {
                    SharedString::from(format!(
                        "[{}] {} | {} -> {} | {} -> {}",
                        status_label(&e.status, en),
                        e.relative_path,
                        e.left_size.map(format_size).unwrap_or_else(|| "-".into()),
                        e.right_size.map(format_size).unwrap_or_else(|| "-".into()),
                        e.left_hash.clone().unwrap_or_else(|| "-".into()),
                        e.right_hash.clone().unwrap_or_else(|| "-".into())
                    ))
                })
                .collect::<Vec<_>>();
            if rows.is_empty() {
                rows.push(SharedString::from(if en {
                    "The selected versions have no differences."
                } else {
                    "所选两个版本之间没有差异。"
                }));
            }
            rows
        })
        .unwrap_or_else(|| {
            vec![SharedString::from(if en {
                "No comparison data."
            } else {
                "暂无对比结果。"
            })]
        })
}

fn selected_version_id(state: &UiState) -> Option<i64> {
    state
        .dashboard
        .versions
        .get(state.selected_version_index)
        .map(|v| v.id)
}

fn is_en(settings: &AppSettings) -> bool {
    settings.language == "en"
}

fn tr<'a>(en: bool, zh: &'a str, en_text: &'a str) -> &'a str {
    if en { en_text } else { zh }
}

fn status_label(status: &ChangeStatus, en: bool) -> &'static str {
    if en {
        status.short_label()
    } else {
        match status {
            ChangeStatus::Added => "新增",
            ChangeStatus::Modified => "修改",
            ChangeStatus::Deleted => "删除",
        }
    }
}

fn compute_health(dashboard: &WorkspaceData) -> String {
    let mut hasher = blake3::Hasher::new();
    hasher.update(dashboard.workspace_path.as_bytes());
    hasher.update(dashboard.total_files.to_string().as_bytes());
    hasher.update(dashboard.changed_files.to_string().as_bytes());
    hasher.finalize().to_hex()[..12].to_string()
}

fn status_message(en: bool, key: &str, error: &str) -> (String, String) {
    let (title, body) = match key {
        "workspace_opened" => (
            tr(en, "工作区已打开", "Workspace Opened"),
            tr(
                en,
                "主界面已切换到新的工作区数据。",
                "The main view now points to the selected workspace.",
            ),
        ),
        "refresh_complete" => (
            tr(en, "刷新完成", "Refresh Complete"),
            tr(
                en,
                "工作区已经重新扫描，列表已更新。",
                "The workspace was rescanned and all lists were updated.",
            ),
        ),
        "version_created" => (
            tr(en, "版本已创建", "Version Created"),
            tr(
                en,
                "当前工作区已经保存为一个新版本。",
                "The current workspace has been saved as a new version.",
            ),
        ),
        "details_loaded" => (
            tr(en, "详情已加载", "Details Loaded"),
            tr(
                en,
                "版本详情和文件预览已经打开。",
                "Version details and file preview are now open.",
            ),
        ),
        "compare_loaded" => (
            tr(en, "对比完成", "Compare Ready"),
            tr(
                en,
                "当前已显示所选两个版本之间的差异。",
                "Differences between the two selected versions are now shown.",
            ),
        ),
        "rollback_ready" => (
            tr(en, "等待确认", "Waiting for Confirmation"),
            tr(
                en,
                "请确认是否回滚到当前选中的版本。",
                "Please confirm whether to roll back to the selected version.",
            ),
        ),
        "rollback_done" => (
            tr(en, "回滚完成", "Rollback Complete"),
            tr(
                en,
                "工作区已经恢复到选中的版本内容。",
                "The workspace has been restored to the selected version.",
            ),
        ),
        "settings_saved" => (
            tr(en, "设置已保存", "Settings Saved"),
            tr(
                en,
                "语言和回滚设置已经立即生效。",
                "Language and rollback settings have been applied.",
            ),
        ),
        "need_version" => (
            tr(en, "请先选择版本", "Choose a Version"),
            tr(
                en,
                "请先在右侧版本历史中选中一个版本。",
                "Select a version from the history list first.",
            ),
        ),
        "need_compare_pair" => (
            tr(en, "缺少对比对象", "Compare Pair Missing"),
            tr(
                en,
                "当前没有足够的版本可供对比。",
                "There are not enough versions available to compare.",
            ),
        ),
        "error" => (tr(en, "操作失败", "Action Failed"), error),
        _ => (
            tr(en, "状态", "Status"),
            tr(
                en,
                "可以打开工作区、创建版本、查看详情、执行版本对比，以及确认回滚。",
                "You can open a workspace, create versions, inspect details, compare versions, and confirm rollbacks.",
            ),
        ),
    };
    (title.into(), body.into())
}

fn set_status(app: &AppWindow, en: bool, key: &str, error: &str) {
    let (title, body) = status_message(en, key, error);
    app.set_status_title(title.into());
    app.set_status_body(body.into());
}

fn format_size(size: u64) -> String {
    const KB: f64 = 1024.0;
    const MB: f64 = KB * 1024.0;
    if size == 0 {
        "0 B".into()
    } else if size as f64 >= MB {
        format!("{:.1} MB", size as f64 / MB)
    } else if size as f64 >= KB {
        format!("{:.1} KB", size as f64 / KB)
    } else {
        format!("{size} B")
    }
}

fn constrain_window_height(app: &AppWindow) {
    let max_height = screen_work_area_height()
        .map(|value| value.saturating_sub(32).max(640))
        .unwrap_or(700);
    app.window()
        .set_size(LogicalSize::new(1040.0, max_height.min(700) as f32));
}

#[cfg(target_os = "windows")]
fn screen_work_area_height() -> Option<u32> {
    use windows::Win32::Foundation::RECT;
    use windows::Win32::UI::WindowsAndMessaging::{
        SPI_GETWORKAREA, SPIF_SENDCHANGE, SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS,
        SystemParametersInfoW,
    };
    let mut rect = RECT::default();
    let ok = unsafe {
        SystemParametersInfoW(
            SPI_GETWORKAREA,
            0,
            Some((&mut rect as *mut RECT).cast()),
            SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS(SPIF_SENDCHANGE.0),
        )
    }
    .is_ok();
    if ok {
        Some((rect.bottom - rect.top).max(0) as u32)
    } else {
        None
    }
}

#[cfg(not(target_os = "windows"))]
fn screen_work_area_height() -> Option<u32> {
    None
}
