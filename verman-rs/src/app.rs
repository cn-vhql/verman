use crate::api;
use crate::models::{
    ChangeEntry, ContextMenuStatus, ExportResult, StatusNotice, VersionDetails, VersionDiffEntry,
    VersionDiffResult, VersionEntry, VersionFilePreview, WorkspaceData,
};
use leptos::ev::SubmitEvent;
use leptos::prelude::*;
use leptos::task::spawn_local;
use similar::{ChangeTag, TextDiff};
use std::sync::Arc;
use wasm_bindgen::JsCast;
use web_sys::{HtmlInputElement, HtmlSelectElement, HtmlTextAreaElement};

const MENU_PROJECT: &str = "project";
const MENU_VERSION: &str = "version";
const MENU_SETTINGS: &str = "settings";
const DIALOG_COMMIT: &str = "commit";
const DIALOG_DETAILS: &str = "details";
const DIALOG_COMPARE: &str = "compare";
const DIALOG_IGNORE: &str = "ignore";
const DIALOG_CONTEXT: &str = "context";
const DIALOG_LANGUAGE: &str = "language";
const DIALOG_ROLLBACK_CONFIRM: &str = "rollback-confirm";

#[component]
pub fn App() -> impl IntoView {
    let initial_language = api::get_preferred_language();
    let dashboard = RwSignal::new(None::<WorkspaceData>);
    let workspace_path = RwSignal::new(None::<String>);
    let selected_version_id = RwSignal::new(None::<i64>);
    let compare_left_id = RwSignal::new(None::<i64>);
    let compare_right_id = RwSignal::new(None::<i64>);
    let compare_result = RwSignal::new(None::<VersionDiffResult>);
    let version_details = RwSignal::new(None::<VersionDetails>);
    let selected_detail_path = RwSignal::new(None::<String>);
    let file_preview = RwSignal::new(None::<VersionFilePreview>);
    let preview_loading = RwSignal::new(false);
    let context_menu_status = RwSignal::new(None::<ContextMenuStatus>);
    let ignore_rules_draft = RwSignal::new(String::new());
    let description = RwSignal::new(String::new());
    let backup_current = RwSignal::new(true);
    let is_busy = RwSignal::new(false);
    let menu_open = RwSignal::new(None::<&'static str>);
    let active_dialog = RwSignal::new(None::<&'static str>);
    let language = RwSignal::new(initial_language.clone());
    let is_mock_mode = api::is_mock_mode();
    let status_notice = RwSignal::new(Some(StatusNotice {
        title: tr(&initial_language, "就绪", "Ready"),
        body: if is_mock_mode {
            tr(
                &initial_language,
                "当前是浏览器预览模式，界面调试使用的是模拟数据。",
                "Browser preview mode is using mock data for UI development.",
            )
        } else {
            tr(
                &initial_language,
                "请选择一个工作区，开始查看变更和版本记录。",
                "Choose a workspace to start browsing changes and version history.",
            )
        },
    }));

    let apply_loaded_data = move |data: WorkspaceData| {
        let selected = data.versions.first().map(|entry| entry.id);
        let compare_left = data.versions.get(1).map(|entry| entry.id).or(selected);
        let compare_right = selected;
        ignore_rules_draft.set(data.ignore_rules.clone());
        workspace_path.set(Some(data.workspace_path.clone()));
        selected_version_id.set(selected);
        compare_left_id.set(compare_left);
        compare_right_id.set(compare_right);
        dashboard.set(Some(data));
        compare_result.set(None);
        version_details.set(None);
        selected_detail_path.set(None);
        file_preview.set(None);
    };

    let refresh_context_menu = move || {
        spawn_local(async move {
            match api::get_context_menu_status().await {
                Ok(status) => context_menu_status.set(Some(status)),
                Err(error) => {
                    let lang = language.get_untracked();
                    status_notice.set(Some(StatusNotice {
                        title: tr(
                            &lang,
                            "读取右键菜单状态失败",
                            "Failed to read context menu status",
                        ),
                        body: error,
                    }))
                }
            }
        });
    };

    let load_workspace = move |path: String, announce: String| {
        let lang = language.get_untracked();
        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: announce,
            body: tr(
                &lang,
                "正在扫描工作区并同步版本数据...",
                "Scanning the workspace and syncing version data...",
            ),
        }));

        spawn_local(async move {
            match api::open_workspace(&path).await {
                Ok(data) => {
                    apply_loaded_data(data);
                    let lang = language.get_untracked();
                    status_notice.set(Some(StatusNotice {
                        title: tr(&lang, "工作区已打开", "Workspace opened"),
                        body: tr(
                            &lang,
                            "文件变更、版本历史和设置已经同步完成。",
                            "Changes, version history, and settings are now in sync.",
                        ),
                    }));
                }
                Err(error) => {
                    dashboard.set(None);
                    workspace_path.set(None);
                    compare_result.set(None);
                    version_details.set(None);
                    selected_detail_path.set(None);
                    file_preview.set(None);
                    let lang = language.get_untracked();
                    status_notice.set(Some(StatusNotice {
                        title: tr(&lang, "工作区打开失败", "Failed to open workspace"),
                        body: error,
                    }));
                }
            }

            is_busy.set(false);
        });
    };

    refresh_context_menu();
    if is_mock_mode {
        load_workspace(
            "H:/pythonwork/verman".to_string(),
            tr(&initial_language, "加载浏览器预览", "Load browser preview"),
        );
    } else {
        spawn_local(async move {
            if let Ok(context) = api::get_launch_context().await {
                if let Some(path) = context.startup_path {
                    let lang = language.get_untracked();
                    load_workspace(path, tr(&lang, "打开启动路径", "Open startup path"));
                }
            }
        });
    }

    let pick_workspace = move |_| {
        menu_open.set(None);
        let lang = language.get_untracked();
        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: tr(&lang, "选择工作区", "Choose workspace"),
            body: tr(
                &lang,
                "等待系统文件夹选择器...",
                "Waiting for the system folder picker...",
            ),
        }));

        spawn_local(async move {
            match api::pick_workspace().await {
                Ok(Some(path)) => {
                    let lang = language.get_untracked();
                    load_workspace(path, tr(&lang, "打开工作区", "Open workspace"))
                }
                Ok(None) => {
                    is_busy.set(false);
                    let lang = language.get_untracked();
                    status_notice.set(Some(StatusNotice {
                        title: tr(&lang, "已取消", "Cancelled"),
                        body: tr(&lang, "没有选择任何工作区。", "No workspace was selected."),
                    }));
                }
                Err(error) => {
                    is_busy.set(false);
                    let lang = language.get_untracked();
                    status_notice.set(Some(StatusNotice {
                        title: tr(&lang, "选择工作区失败", "Failed to choose workspace"),
                        body: error,
                    }));
                }
            }
        });
    };

    let refresh_workspace = move |_| {
        menu_open.set(None);
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };

        let lang = language.get_untracked();
        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: tr(&lang, "刷新数据", "Refresh data"),
            body: tr(
                &lang,
                "正在重新扫描文件并读取最新版本数据...",
                "Rescanning files and loading the latest version data...",
            ),
        }));

        spawn_local(async move {
            match api::refresh_workspace(&path).await {
                Ok(data) => {
                    apply_loaded_data(data);
                    let lang = language.get_untracked();
                    status_notice.set(Some(StatusNotice {
                        title: tr(&lang, "刷新完成", "Refresh complete"),
                        body: tr(
                            &lang,
                            "主界面已经更新到当前工作区的最新状态。",
                            "The main view is now updated to the latest workspace state.",
                        ),
                    }));
                }
                Err(error) => {
                    let lang = language.get_untracked();
                    status_notice.set(Some(StatusNotice {
                        title: tr(&lang, "刷新失败", "Refresh failed"),
                        body: error,
                    }))
                }
            }

            is_busy.set(false);
        });
    };

    let open_commit_dialog = move |_| {
        menu_open.set(None);
        active_dialog.set(Some(DIALOG_COMMIT));
    };

    let open_compare_dialog = move |_| {
        menu_open.set(None);
        active_dialog.set(Some(DIALOG_COMPARE));
    };

    let open_ignore_dialog = move |_| {
        menu_open.set(None);
        active_dialog.set(Some(DIALOG_IGNORE));
    };

    let open_context_dialog = move |_| {
        menu_open.set(None);
        active_dialog.set(Some(DIALOG_CONTEXT));
    };

    let open_language_dialog = move |_| {
        menu_open.set(None);
        active_dialog.set(Some(DIALOG_LANGUAGE));
    };

    let change_language = move |next_language: &'static str| {
        api::set_preferred_language(next_language);
        language.set(next_language.to_string());
        active_dialog.set(None);
        status_notice.set(Some(StatusNotice {
            title: tr(next_language, "语言已切换", "Language updated"),
            body: tr(
                next_language,
                "界面语言设置已保存，后续打开应用时会继续使用当前语言。",
                "The interface language has been saved and will be reused next time.",
            ),
        }));
    };

    let load_file_preview = Callback::new(move |relative_path: String| {
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let Some(version_id) = selected_version_id.get_untracked() else {
            return;
        };

        preview_loading.set(true);
        selected_detail_path.set(Some(relative_path.clone()));
        spawn_local(async move {
            match api::get_version_file_preview(&path, version_id, &relative_path).await {
                Ok(preview) => file_preview.set(Some(preview)),
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "读取文件预览失败".to_string(),
                    body: error,
                })),
            }
            preview_loading.set(false);
        });
    });

    let open_details_dialog = move |_| {
        menu_open.set(None);
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let Some(version_id) = selected_version_id.get_untracked() else {
            status_notice.set(Some(StatusNotice {
                title: "请先选择版本".to_string(),
                body: "先在版本历史里选中一个历史版本，再查看变更详情。".to_string(),
            }));
            return;
        };

        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "读取版本详情".to_string(),
            body: "正在加载该版本的变更文件和预览信息...".to_string(),
        }));

        spawn_local(async move {
            match api::get_version_details(&path, version_id).await {
                Ok(details) => {
                    let first_path = details.files.first().map(|file| file.relative_path.clone());
                    version_details.set(Some(details));
                    active_dialog.set(Some(DIALOG_DETAILS));
                    file_preview.set(None);
                    selected_detail_path.set(None);
                    if let Some(relative_path) = first_path {
                        load_file_preview.run(relative_path);
                    }
                }
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "读取版本详情失败".to_string(),
                    body: error,
                })),
            }

            is_busy.set(false);
        });
    };

    let open_preview_external = move |_| {
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let Some(version_id) = selected_version_id.get_untracked() else {
            return;
        };
        let Some(relative_path) = selected_detail_path.get_untracked() else {
            return;
        };

        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "打开历史文件".to_string(),
            body: "正在导出到临时目录并调用系统默认程序...".to_string(),
        }));

        spawn_local(async move {
            match api::open_version_file_external(&path, version_id, &relative_path).await {
                Ok(result) => status_notice.set(Some(StatusNotice {
                    title: "历史文件已打开".to_string(),
                    body: format!("已写入临时文件：{}", result.temp_path),
                })),
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "打开历史文件失败".to_string(),
                    body: error,
                })),
            }
            is_busy.set(false);
        });
    };

    let submit_version = move |event: SubmitEvent| {
        event.prevent_default();

        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let message = description.get_untracked();
        if message.trim().is_empty() {
            status_notice.set(Some(StatusNotice {
                title: "版本说明不能为空".to_string(),
                body: "请输入本次版本的简短描述。".to_string(),
            }));
            return;
        }

        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "正在提交版本".to_string(),
            body: "Rust 正在计算快照并写入本地数据...".to_string(),
        }));

        spawn_local(async move {
            match api::create_version(&path, &message).await {
                Ok(data) => {
                    description.set(String::new());
                    apply_loaded_data(data);
                    active_dialog.set(None);
                    status_notice.set(Some(StatusNotice {
                        title: "版本已创建".to_string(),
                        body: "新的快照已经加入版本历史。".to_string(),
                    }));
                }
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "提交版本失败".to_string(),
                    body: error,
                })),
            }

            is_busy.set(false);
        });
    };

    let request_rollback_selected = move |_| {
        menu_open.set(None);
        let Some(_) = workspace_path.get_untracked() else {
            return;
        };
        let Some(_) = selected_version_id.get_untracked() else {
            status_notice.set(Some(StatusNotice {
                title: "请先选择版本".to_string(),
                body: "点击右侧版本列表中的一条记录后再执行回滚。".to_string(),
            }));
            return;
        };

        active_dialog.set(Some(DIALOG_ROLLBACK_CONFIRM));
    };

    let rollback_selected = move |_| {
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let Some(version_id) = selected_version_id.get_untracked() else {
            return;
        };

        let should_backup = backup_current.get_untracked();
        active_dialog.set(None);
        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "正在回滚".to_string(),
            body: if should_backup {
                "会先备份当前工作区，再恢复到所选版本。".to_string()
            } else {
                "将直接恢复所选版本，不额外创建备份。".to_string()
            },
        }));

        spawn_local(async move {
            match api::rollback_version(&path, version_id, should_backup).await {
                Ok(data) => {
                    apply_loaded_data(data);
                    selected_version_id.set(Some(version_id));
                    status_notice.set(Some(StatusNotice {
                        title: "回滚完成".to_string(),
                        body: "当前工作区已经恢复到所选版本。".to_string(),
                    }));
                }
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "回滚失败".to_string(),
                    body: error,
                })),
            }

            is_busy.set(false);
        });
    };

    let run_compare = move |_| {
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let Some(left_version_id) = compare_left_id.get_untracked() else {
            status_notice.set(Some(StatusNotice {
                title: "请选择基准版本".to_string(),
                body: "先选择两个版本，再执行对比。".to_string(),
            }));
            return;
        };
        let Some(right_version_id) = compare_right_id.get_untracked() else {
            status_notice.set(Some(StatusNotice {
                title: "请选择目标版本".to_string(),
                body: "先选择两个版本，再执行对比。".to_string(),
            }));
            return;
        };

        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "正在比较版本".to_string(),
            body: "正在生成两个快照之间的文件差异...".to_string(),
        }));

        spawn_local(async move {
            match api::compare_versions(&path, left_version_id, right_version_id).await {
                Ok(result) => {
                    compare_result.set(Some(result));
                    status_notice.set(Some(StatusNotice {
                        title: "版本对比完成".to_string(),
                        body: "对比结果已经更新到弹窗中。".to_string(),
                    }));
                }
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "版本对比失败".to_string(),
                    body: error,
                })),
            }

            is_busy.set(false);
        });
    };

    let export_selected = move |_| {
        menu_open.set(None);
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let Some(version_id) = selected_version_id.get_untracked() else {
            status_notice.set(Some(StatusNotice {
                title: "请先选择版本".to_string(),
                body: "先在版本历史里选择一条版本记录，再执行导出。".to_string(),
            }));
            return;
        };

        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "选择导出目录".to_string(),
            body: "请选择用于导出版本文件的目标目录。".to_string(),
        }));

        spawn_local(async move {
            match api::pick_export_directory().await {
                Ok(Some(target)) => match api::export_version(&path, version_id, &target).await {
                    Ok(ExportResult {
                        target_path,
                        file_count,
                    }) => status_notice.set(Some(StatusNotice {
                        title: "导出完成".to_string(),
                        body: format!("已导出 {file_count} 个文件到 {target_path}。"),
                    })),
                    Err(error) => status_notice.set(Some(StatusNotice {
                        title: "导出失败".to_string(),
                        body: error,
                    })),
                },
                Ok(None) => status_notice.set(Some(StatusNotice {
                    title: "已取消导出".to_string(),
                    body: "没有选择导出目录。".to_string(),
                })),
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "导出目录选择失败".to_string(),
                    body: error,
                })),
            }

            is_busy.set(false);
        });
    };

    let save_ignore_rules = move |_| {
        let Some(path) = workspace_path.get_untracked() else {
            return;
        };
        let contents = ignore_rules_draft.get_untracked();

        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "保存忽略规则".to_string(),
            body: "正在写入 .vermanignore 并重新扫描工作区...".to_string(),
        }));

        spawn_local(async move {
            match api::save_ignore_rules(&path, &contents).await {
                Ok(data) => {
                    apply_loaded_data(data);
                    active_dialog.set(None);
                    status_notice.set(Some(StatusNotice {
                        title: "忽略规则已更新".to_string(),
                        body: "新的扫描规则已经生效。".to_string(),
                    }));
                }
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "保存忽略规则失败".to_string(),
                    body: error,
                })),
            }

            is_busy.set(false);
        });
    };

    let install_context_menu = move |_| {
        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "安装右键菜单".to_string(),
            body: "正在注册 Windows 资源管理器右键菜单...".to_string(),
        }));

        spawn_local(async move {
            match api::install_context_menu().await {
                Ok(status) => {
                    context_menu_status.set(Some(status));
                    status_notice.set(Some(StatusNotice {
                        title: "右键菜单已安装".to_string(),
                        body: "现在可以在资源管理器里用 VerMan 打开目录。".to_string(),
                    }));
                }
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "安装右键菜单失败".to_string(),
                    body: error,
                })),
            }
            is_busy.set(false);
        });
    };

    let uninstall_context_menu = move |_| {
        is_busy.set(true);
        status_notice.set(Some(StatusNotice {
            title: "卸载右键菜单".to_string(),
            body: "正在移除资源管理器中的 VerMan 集成...".to_string(),
        }));

        spawn_local(async move {
            match api::uninstall_context_menu().await {
                Ok(status) => {
                    context_menu_status.set(Some(status));
                    status_notice.set(Some(StatusNotice {
                        title: "右键菜单已移除".to_string(),
                        body: "资源管理器集成已经关闭。".to_string(),
                    }));
                }
                Err(error) => status_notice.set(Some(StatusNotice {
                    title: "移除右键菜单失败".to_string(),
                    body: error,
                })),
            }
            is_busy.set(false);
        });
    };

    view! {
        <main class="app-shell" on:click=move |_| menu_open.set(None)>
            <header class="menu-bar" on:click=move |event| event.stop_propagation()>
                <div class="brand-area">
                    <div class="brand-mark">"VerMan"</div>
                        <div class="brand-copy">"留旧卷以知新，循微痕而复始"</div>
                </div>

                <nav class="menu-nav">
                    <div class="menu-wrap" on:click=move |event| event.stop_propagation()>
                        <button
                            class="menu-button"
                            on:click=move |_| {
                                if menu_open.get() == Some(MENU_PROJECT) {
                                    menu_open.set(None);
                                } else {
                                    menu_open.set(Some(MENU_PROJECT));
                                }
                            }
                        >
                            {move || tr(&language.get(), "项目", "Project")}
                        </button>
                        <Show when=move || menu_open.get() == Some(MENU_PROJECT)>
                            <div class="menu-dropdown">
                                <button class="menu-action" on:click=pick_workspace>
                                    {move || tr(&language.get(), "打开工作区...", "Open workspace...")}
                                </button>
                                <button
                                    class="menu-action"
                                    on:click=refresh_workspace
                                    disabled=move || workspace_path.get().is_none()
                                >
                                    {move || tr(&language.get(), "刷新当前工作区", "Refresh current workspace")}
                                </button>
                            </div>
                        </Show>
                    </div>

                    <div class="menu-wrap" on:click=move |event| event.stop_propagation()>
                        <button
                            class="menu-button"
                            on:click=move |_| {
                                if menu_open.get() == Some(MENU_VERSION) {
                                    menu_open.set(None);
                                } else {
                                    menu_open.set(Some(MENU_VERSION));
                                }
                            }
                        >
                            {move || tr(&language.get(), "版本", "Version")}
                        </button>
                        <Show when=move || menu_open.get() == Some(MENU_VERSION)>
                            <div class="menu-dropdown">
                                <button
                                    class="menu-action"
                                    on:click=open_commit_dialog
                                    disabled=move || workspace_path.get().is_none()
                                >
                                    {move || tr(&language.get(), "提交版本...", "Create version...")}
                                </button>
                                <button
                                    class="menu-action"
                                    on:click=open_details_dialog
                                    disabled=move || selected_version_id.get().is_none()
                                >
                                    {move || tr(&language.get(), "查看变更详情...", "View change details...")}
                                </button>
                                <button
                                    class="menu-action"
                                    on:click=request_rollback_selected
                                    disabled=move || selected_version_id.get().is_none()
                                >
                                    {move || tr(&language.get(), "回滚选中版本", "Rollback selected version")}
                                </button>
                                <button
                                    class="menu-action"
                                    on:click=export_selected
                                    disabled=move || selected_version_id.get().is_none()
                                >
                                    {move || tr(&language.get(), "导出选中版本...", "Export selected version...")}
                                </button>
                                <button
                                    class="menu-action"
                                    on:click=open_compare_dialog
                                    disabled=move || workspace_path.get().is_none()
                                >
                                    {move || tr(&language.get(), "版本对比...", "Compare versions...")}
                                </button>
                            </div>
                        </Show>
                    </div>

                    <div class="menu-wrap" on:click=move |event| event.stop_propagation()>
                        <button
                            class="menu-button"
                            on:click=move |_| {
                                if menu_open.get() == Some(MENU_SETTINGS) {
                                    menu_open.set(None);
                                } else {
                                    menu_open.set(Some(MENU_SETTINGS));
                                }
                            }
                        >
                            {move || tr(&language.get(), "设置", "Settings")}
                        </button>
                        <Show when=move || menu_open.get() == Some(MENU_SETTINGS)>
                            <div class="menu-dropdown">
                                <button class="menu-action" on:click=open_language_dialog>
                                    {move || tr(&language.get(), "语言...", "Language...")}
                                </button>
                                <button
                                    class="menu-action"
                                    on:click=open_ignore_dialog
                                    disabled=move || workspace_path.get().is_none()
                                >
                                    {move || tr(&language.get(), "忽略规则...", "Ignore rules...")}
                                </button>
                                <button class="menu-action" on:click=open_context_dialog>
                                    {move || tr(&language.get(), "右键菜单集成...", "Explorer integration...")}
                                </button>
                            </div>
                        </Show>
                    </div>
                </nav>

                <div class="menu-state">
                    <Show when=move || is_mock_mode>
                        <span class="state-badge">{move || tr(&language.get(), "浏览器预览", "Browser preview")}</span>
                    </Show>
                </div>
            </header>

            <section class="workspace-strip">
                <div class="workspace-main">
                    <div class="panel-label">{move || tr(&language.get(), "当前工作区", "Current workspace")}</div>
                    <div class="workspace-path">
                        {move || workspace_path.get().unwrap_or_else(|| tr(&language.get(), "尚未打开工作区", "No workspace opened yet"))}
                    </div>
                </div>

                <div class="summary-grid">
                    <SummaryCard
                        label=move || tr(&language.get(), "文件", "Files")
                        value=move || dashboard.get().map(|data| data.total_files).unwrap_or_default().to_string()
                    />
                    <SummaryCard
                        label=move || tr(&language.get(), "变更", "Changes")
                        value=move || dashboard.get().map(|data| data.changed_files).unwrap_or_default().to_string()
                    />
                    <SummaryCard
                        label=move || tr(&language.get(), "版本", "Versions")
                        value=move || dashboard.get().map(|data| data.total_versions).unwrap_or_default().to_string()
                    />
                    <SummaryCard
                        label=move || tr(&language.get(), "选中", "Selected")
                        value=move || {
                            dashboard
                                .get()
                                .and_then(|data| {
                                    data.versions
                                        .into_iter()
                                        .find(|version| Some(version.id) == selected_version_id.get())
                                        .map(|version| version.version_number)
                                })
                                .unwrap_or_else(|| "-".to_string())
                        }
                    />
                </div>
            </section>

            <Show
                when=move || dashboard.get().is_some()
                fallback=move || {
                    view! {
                        <section class="empty-panel">
                            <div class="empty-title">{move || tr(&language.get(), "请选择一个工作区", "Choose a workspace")}</div>
                            <div class="empty-copy">
                                {move || tr(&language.get(), "打开目录后，你可以在这里查看文件变更、管理版本历史，并通过顶部菜单执行导出、对比和右键菜单设置。", "After opening a folder, you can inspect file changes, manage version history, and use the top menu for export, compare, and context menu settings.")}
                            </div>
                            <button class="primary-button" on:click=pick_workspace>
                                {move || tr(&language.get(), "打开工作区", "Open workspace")}
                            </button>
                        </section>
                    }
                }
            >
                {move || {
                    let data = dashboard.get().unwrap_or_default();
                    view! {
                        <section class="content-grid">
                            <ChangesPanel items=data.changes.clone() language=language />
                            <VersionsPanel items=data.versions.clone() selected=selected_version_id language=language />
                        </section>
                    }
                }}
            </Show>

            <section class="toolbar">
                <label class="check-row" for="backup-check">
                    <input
                        id="backup-check"
                        class="checkbox"
                        type="checkbox"
                        prop:checked=move || backup_current.get()
                        on:change=move |event| {
                            let target = event.target().unwrap().unchecked_into::<HtmlInputElement>();
                            backup_current.set(target.checked());
                        }
                    />
                    <span>{move || tr(&language.get(), "回滚前备份当前工作区", "Back up current workspace before rollback")}</span>
                </label>

                <div class="toolbar-actions">
                    <button
                        class="secondary-button"
                        on:click=open_details_dialog
                        disabled=move || is_busy.get() || selected_version_id.get().is_none()
                    >
                        {move || tr(&language.get(), "查看详情", "View details")}
                    </button>
                    <button
                        class="secondary-button"
                        on:click=refresh_workspace
                        disabled=move || is_busy.get() || workspace_path.get().is_none()
                    >
                        {move || tr(&language.get(), "刷新", "Refresh")}
                    </button>
                    <button
                        class="secondary-button"
                        on:click=request_rollback_selected
                        disabled=move || is_busy.get() || selected_version_id.get().is_none()
                    >
                        {move || tr(&language.get(), "回滚选中版本", "Rollback selected version")}
                    </button>
                    <button
                        class="primary-button"
                        on:click=open_commit_dialog
                        disabled=move || is_busy.get() || workspace_path.get().is_none()
                    >
                        {move || tr(&language.get(), "提交版本", "Create version")}
                    </button>
                </div>
            </section>

            <footer class="status-bar">
                <div class="status-head">
                    {move || {
                        status_notice
                            .get()
                            .map(|notice| notice.title)
                            .unwrap_or_else(|| "就绪".to_string())
                    }}
                </div>
                <div class="status-text">
                    {move || {
                        status_notice
                            .get()
                            .map(|notice| notice.body)
                            .unwrap_or_else(|| tr(&language.get(), "等待下一步操作。", "Waiting for your next action."))
                    }}
                </div>
                <div class="status-side">
                    {move || {
                        if workspace_path.get().is_some() {
                            tr(&language.get(), "数据库已连接", "Database connected")
                        } else {
                            tr(&language.get(), "未打开项目", "No project opened")
                        }
                    }}
                </div>
            </footer>

            <Show when=move || active_dialog.get().is_some()>
                <div class="modal-backdrop" on:click=move |_| active_dialog.set(None)>
                    <Show when=move || active_dialog.get() == Some(DIALOG_COMMIT)>
                        <section class="modal-card" on:click=move |event| event.stop_propagation()>
                            <div class="modal-header">
                                <div>
                                    <div class="panel-label">"提交版本"</div>
                                    <div class="panel-label">{move || tr(&language.get(), "提交版本", "Create version")}</div>
                                    <div class="modal-title">{move || tr(&language.get(), "输入本次版本说明", "Describe this version")}</div>
                                </div>
                                <button class="icon-button" on:click=move |_| active_dialog.set(None)>
                                    {move || tr(&language.get(), "关闭", "Close")}
                                </button>
                            </div>

                            <form class="modal-form" on:submit=submit_version>
                                <textarea
                                    class="textarea commit-editor"
                                    placeholder=move || tr(&language.get(), "例如：补齐 Rust 版版本对比与导出逻辑，修正忽略规则扫描", "Example: finish Rust compare/export flow and fix ignore-rule scanning")
                                    prop:value=move || description.get()
                                    on:input=move |event| {
                                        let target = event.target().unwrap().unchecked_into::<HtmlTextAreaElement>();
                                        description.set(target.value());
                                    }
                                />

                                <div class="modal-actions">
                                    <button class="secondary-button" type="button" on:click=move |_| active_dialog.set(None)>
                                        {move || tr(&language.get(), "取消", "Cancel")}
                                    </button>
                                    <button class="primary-button" type="submit">
                                        {move || tr(&language.get(), "提交版本", "Create version")}
                                    </button>
                                </div>
                            </form>
                        </section>
                    </Show>

                    <Show when=move || active_dialog.get() == Some(DIALOG_DETAILS)>
                        <section class="modal-card modal-large details-modal" on:click=move |event| event.stop_propagation()>
                            <div class="modal-header">
                                <div>
                                    <div class="panel-label">{move || tr(&language.get(), "版本详情", "Version details")}</div>
                                    <div class="modal-title">{move || tr(&language.get(), "查看历史版本的变更与文件内容", "Browse file changes and contents in this version")}</div>
                                </div>
                                <button class="icon-button" on:click=move |_| active_dialog.set(None)>
                                    {move || tr(&language.get(), "关闭", "Close")}
                                </button>
                            </div>

                            <VersionDetailsPanel
                                details=version_details
                                language=language
                                selected_path=selected_detail_path
                                preview=file_preview
                                preview_loading=preview_loading
                                on_select_preview=load_file_preview
                                on_open_external=Callback::new(move |_| open_preview_external(()))
                            />
                        </section>
                    </Show>

                    <Show when=move || active_dialog.get() == Some(DIALOG_COMPARE)>
                        <section class="modal-card modal-large" on:click=move |event| event.stop_propagation()>
                            <div class="modal-header">
                                <div>
                                    <div class="panel-label">{move || tr(&language.get(), "版本对比", "Version comparison")}</div>
                                    <div class="modal-title">{move || tr(&language.get(), "比较两个版本之间的文件差异", "Compare the file differences between two versions")}</div>
                                </div>
                                <button class="icon-button" on:click=move |_| active_dialog.set(None)>
                                    {move || tr(&language.get(), "关闭", "Close")}
                                </button>
                            </div>

                            {move || {
                                let versions = dashboard
                                    .get()
                                    .map(|data| data.versions)
                                    .unwrap_or_default();
                                view! {
                                    <div class="modal-stack">
                                        <ComparePanel
                                            versions=versions
                                            language=language
                                            compare_left=compare_left_id
                                            compare_right=compare_right_id
                                            on_compare=Callback::new(move |_| run_compare(()))
                                        />
                                        <DiffPanel result=compare_result language=language />
                                    </div>
                                }
                            }}
                        </section>
                    </Show>

                    <Show when=move || active_dialog.get() == Some(DIALOG_IGNORE)>
                        <section class="modal-card" on:click=move |event| event.stop_propagation()>
                            <div class="modal-header">
                                <div>
                                    <div class="panel-label">{move || tr(&language.get(), "忽略规则", "Ignore rules")}</div>
                                    <div class="modal-title">{move || tr(&language.get(), "设置不参与扫描的文件模式", "Set file patterns excluded from scanning")}</div>
                                </div>
                                <button class="icon-button" on:click=move |_| active_dialog.set(None)>
                                    {move || tr(&language.get(), "关闭", "Close")}
                                </button>
                            </div>

                            <IgnoreRulesPanel
                                language=language
                                draft=ignore_rules_draft
                                on_save=Callback::new(move |_| save_ignore_rules(()))
                            />
                        </section>
                    </Show>

                    <Show when=move || active_dialog.get() == Some(DIALOG_LANGUAGE)>
                        <section class="modal-card" on:click=move |event| event.stop_propagation()>
                            <div class="modal-header">
                                <div>
                                    <div class="panel-label">{move || tr(&language.get(), "语言", "Language")}</div>
                                    <div class="modal-title">{move || tr(&language.get(), "选择界面语言", "Choose interface language")}</div>
                                </div>
                                <button class="icon-button" on:click=move |_| active_dialog.set(None)>
                                    {move || tr(&language.get(), "关闭", "Close")}
                                </button>
                            </div>

                            <LanguagePanel
                                language=language
                                on_change=Callback::new(move |value: String| change_language(if value == "en" { "en" } else { "zh" }))
                            />
                        </section>
                    </Show>

                    <Show when=move || active_dialog.get() == Some(DIALOG_ROLLBACK_CONFIRM)>
                        <section class="modal-card" on:click=move |event| event.stop_propagation()>
                            <div class="modal-header">
                                <div>
                                    <div class="panel-label">{move || tr(&language.get(), "确认回滚", "Confirm rollback")}</div>
                                    <div class="modal-title">{move || tr(&language.get(), "确定要恢复到当前选中的版本吗？", "Restore the workspace to the selected version?")}</div>
                                </div>
                                <button class="icon-button" on:click=move |_| active_dialog.set(None)>
                                    {move || tr(&language.get(), "关闭", "Close")}
                                </button>
                            </div>

                            <div class="modal-stack">
                                <div class="field-note">
                                    {move || {
                                        if backup_current.get() {
                                            tr(&language.get(), "当前开启了“回滚前备份当前工作区”，确认后会先创建备份，再执行回滚。", "Backup before rollback is enabled. After confirmation, the app will create a backup first and then perform the rollback.")
                                        } else {
                                            tr(&language.get(), "当前未开启回滚前备份，确认后会直接恢复到所选版本。", "Backup before rollback is disabled. After confirmation, the workspace will be restored directly to the selected version.")
                                        }
                                    }}
                                </div>
                                <div class="modal-actions">
                                    <button class="secondary-button" on:click=move |_| active_dialog.set(None)>
                                        {move || tr(&language.get(), "取消", "Cancel")}
                                    </button>
                                    <button class="primary-button" on:click=rollback_selected>
                                        {move || tr(&language.get(), "确认回滚", "Confirm rollback")}
                                    </button>
                                </div>
                            </div>
                        </section>
                    </Show>

                    <Show when=move || active_dialog.get() == Some(DIALOG_CONTEXT)>
                        <section class="modal-card" on:click=move |event| event.stop_propagation()>
                            <div class="modal-header">
                                <div>
                                    <div class="panel-label">{move || tr(&language.get(), "右键菜单", "Context menu")}</div>
                                    <div class="modal-title">{move || tr(&language.get(), "管理 Windows 资源管理器集成", "Manage Windows Explorer integration")}</div>
                                </div>
                                <button class="icon-button" on:click=move |_| active_dialog.set(None)>
                                    {move || tr(&language.get(), "关闭", "Close")}
                                </button>
                            </div>

                            <IntegrationPanel
                                language=language
                                status=context_menu_status
                                on_install=Callback::new(move |_| install_context_menu(()))
                                on_uninstall=Callback::new(move |_| uninstall_context_menu(()))
                            />
                        </section>
                    </Show>
                </div>
            </Show>

            <Show when=move || is_busy.get()>
                <div class="busy-overlay">
                    <div class="busy-card">
                        <div class="spinner"></div>
                        <div class="busy-title">{move || tr(&language.get(), "正在处理任务", "Working on your request")}</div>
                        <div class="busy-copy">{move || tr(&language.get(), "扫描、回滚、导出和版本对比会在后台继续执行。", "Scanning, rollback, export, and compare will continue in the background.")}</div>
                    </div>
                </div>
            </Show>
        </main>
    }
}

#[component]
fn SummaryCard<L, F>(label: L, value: F) -> impl IntoView
where
    L: Fn() -> String + Send + Sync + 'static,
    F: Fn() -> String + Send + Sync + 'static,
{
    view! {
        <div class="summary-card">
            <div class="summary-label">{label}</div>
            <div class="summary-value">{value}</div>
        </div>
    }
}

#[component]
fn ChangeRow(item: ChangeEntry, language: RwSignal<String>) -> impl IntoView {
    let status_class_name = status_class(&item.status);
    let status_label = item.status.clone();
    view! {
        <article class="list-row">
            <div class=status_class_name>{move || status_text(&status_label, &language.get())}</div>
            <div class="row-main">
                <div class="row-title">{item.relative_path}</div>
                <div class="row-meta">{format!("BLAKE3 {}", &item.hash.chars().take(12).collect::<String>())}</div>
            </div>
            <div class="row-side">{format_size(item.size)}</div>
        </article>
    }
}

#[component]
fn ChangesPanel(items: Vec<ChangeEntry>, language: RwSignal<String>) -> impl IntoView {
    let total = items.len();
    let items = Arc::new(items);
    view! {
        <section class="panel">
            <div class="panel-header">
                <div>
                    <div class="panel-label">{move || tr(&language.get(), "文件变更", "File changes")}</div>
                    <div class="panel-title">{move || tr(&language.get(), "当前工作区", "Current workspace")}</div>
                </div>
                <div class="panel-badge">{move || format_count(total, &language.get(), "项", "items")}</div>
            </div>

            <div class="list-shell">
                <Show
                    when={
                        let items = items.clone();
                        move || !items.is_empty()
                    }
                    fallback=move || {
                        view! {
                            <div class="empty-inline">
                                <div class="empty-inline-title">{move || tr(&language.get(), "当前没有未提交变更", "There are no uncommitted changes")}</div>
                                <div class="empty-inline-copy">{move || tr(&language.get(), "工作区状态干净，可以直接创建版本。", "The workspace is clean, so you can create a version directly.")}</div>
                            </div>
                        }
                    }
                >
                    <For
                        each={
                            let items = items.clone();
                            move || items.as_ref().clone().into_iter()
                        }
                        key=|item| format!("{}-{}", item.status, item.relative_path)
                        children=move |item| view! { <ChangeRow item=item language=language /> }
                    />
                </Show>
            </div>
        </section>
    }
}

#[component]
fn VersionCard(
    version: VersionEntry,
    selected: RwSignal<Option<i64>>,
    language: RwSignal<String>,
) -> impl IntoView {
    let version_id = version.id;
    let card_class = move || {
        if selected.get() == Some(version_id) {
            "version-row version-row-active"
        } else {
            "version-row"
        }
    };

    view! {
        <article class=card_class on:click=move |_| selected.set(Some(version_id))>
            <div class="version-main">
                <div class="version-head">
                    <div class="version-name">{version.version_number.clone()}</div>
                    <div class="panel-badge">{move || format_count(version.change_count, &language.get(), "项", "items")}</div>
                </div>
                <div class="version-desc">{version.description.clone()}</div>
            </div>
            <div class="version-time">{version.created_at.clone()}</div>
        </article>
    }
}

#[component]
fn VersionsPanel(
    items: Vec<VersionEntry>,
    selected: RwSignal<Option<i64>>,
    language: RwSignal<String>,
) -> impl IntoView {
    let total = items.len();
    let items = Arc::new(items);
    view! {
        <section class="panel">
            <div class="panel-header">
                <div>
                    <div class="panel-label">{move || tr(&language.get(), "版本历史", "Version history")}</div>
                    <div class="panel-title">{move || tr(&language.get(), "已保存版本", "Saved versions")}</div>
                </div>
                <div class="panel-badge">{move || format_count(total, &language.get(), "条", "records")}</div>
            </div>

            <div class="list-shell">
                <Show
                    when={
                        let items = items.clone();
                        move || !items.is_empty()
                    }
                    fallback=move || {
                        view! {
                            <div class="empty-inline">
                                <div class="empty-inline-title">{move || tr(&language.get(), "还没有版本记录", "No version history yet")}</div>
                                <div class="empty-inline-copy">{move || tr(&language.get(), "提交第一个版本后，历史列表会出现在这里。", "The history list will appear here after you create the first version.")}</div>
                            </div>
                        }
                    }
                >
                    <For
                        each={
                            let items = items.clone();
                            move || items.as_ref().clone().into_iter()
                        }
                        key=|version| version.id
                        children=move |version| view! { <VersionCard version=version selected=selected language=language /> }
                    />
                </Show>
            </div>
        </section>
    }
}

#[component]
fn VersionDetailsPanel(
    details: RwSignal<Option<VersionDetails>>,
    language: RwSignal<String>,
    selected_path: RwSignal<Option<String>>,
    preview: RwSignal<Option<VersionFilePreview>>,
    preview_loading: RwSignal<bool>,
    on_select_preview: Callback<String>,
    on_open_external: Callback<()>,
) -> impl IntoView {
    view! {
        <section class="details-layout">
            <div class="details-sidebar">
                {move || {
                    details.get().map(|details| {
                        let version_line =
                            format!("{} · {}", details.version.version_number, details.version.created_at);
                        let description = details.version.description.clone();
                        let add_count = details.stats.add_count;
                        let modify_count = details.stats.modify_count;
                        let delete_count = details.stats.delete_count;
                        let files = details.files.clone();
                        view! {
                            <>
                                <div class="details-summary">
                                    <div class="details-version">{version_line}</div>
                                    <div class="details-description">{description}</div>
                                    <div class="details-stats">
                                        <span class="status-chip status-add">
                                            {move || format!("{} {}", tr(&language.get(), "新增", "Added"), add_count)}
                                        </span>
                                        <span class="status-chip status-modify">
                                            {move || format!("{} {}", tr(&language.get(), "修改", "Modified"), modify_count)}
                                        </span>
                                        <span class="status-chip status-delete">
                                            {move || format!("{} {}", tr(&language.get(), "删除", "Deleted"), delete_count)}
                                        </span>
                                    </div>
                                </div>

                                <div class="details-file-list">
                                    <For
                                        each=move || files.clone().into_iter()
                                        key=|file| format!("{}-{}", file.status, file.relative_path)
                                        children=move |file| {
                                            let relative_path = file.relative_path.clone();
                                            let status_class_name = status_class(&file.status);
                                            let status_label = file.status.clone();
                                            let row_class = move || {
                                                if selected_path.get() == Some(relative_path.clone()) {
                                                    "details-file-row details-file-row-active"
                                                } else {
                                                    "details-file-row"
                                                }
                                            };
                                            let click_path = file.relative_path.clone();
                                            view! {
                                                <button
                                                    class=row_class
                                                    on:click=move |_| on_select_preview.run(click_path.clone())
                                                >
                                                    <span class=status_class_name>{move || status_text(&status_label, &language.get())}</span>
                                                    <span class="details-file-main">
                                                        <span class="details-file-path">{file.relative_path}</span>
                                                        <span class="details-file-meta">
                                                            {move || {
                                                                if file.is_text {
                                                                    tr(&language.get(), "文本文件", "Text file")
                                                                } else {
                                                                    tr(&language.get(), "二进制文件", "Binary file")
                                                                }
                                                            }}
                                                            " · "
                                                            {format_size(file.size)}
                                                        </span>
                                                    </span>
                                                </button>
                                            }
                                        }
                                    />
                                </div>
                            </>
                        }.into_any()
                    }).unwrap_or_else(|| view! {
                        <div class="empty-inline">
                            <div class="empty-inline-title">{move || tr(&language.get(), "没有可显示的版本详情", "No version details to display")}</div>
                            <div class="empty-inline-copy">{move || tr(&language.get(), "请先在主界面选择一个历史版本。", "Select a version from the main view first.")}</div>
                        </div>
                    }.into_any())
                }}
            </div>

            <div class="details-preview">
                <div class="preview-toolbar">
                    <div>
                        <div class="panel-label">{move || tr(&language.get(), "文件预览", "File preview")}</div>
                        <div class="preview-title">
                            {move || selected_path.get().unwrap_or_else(|| tr(&language.get(), "请选择一个变更文件", "Choose a changed file"))}
                        </div>
                    </div>
                    <button
                        class="secondary-button"
                        on:click=move |_| on_open_external.run(())
                        disabled=move || {
                            preview
                                .get()
                                .map(|item| !item.can_open_external)
                                .unwrap_or(true)
                        }
                    >
                        {move || tr(&language.get(), "用系统软件打开", "Open with system app")}
                    </button>
                </div>

                <Show when=move || preview_loading.get()>
                    <div class="preview-loading">{move || tr(&language.get(), "正在加载预览...", "Loading preview...")}</div>
                </Show>

                {move || {
                    preview.get().map(|preview| {
                        let note = preview
                            .note
                            .clone()
                            .filter(|text| !is_generic_preview_note(text));
                        let note_text = note.clone().unwrap_or_default();
                        let is_text = preview.is_text;
                        let left_label = preview.left_label.clone();
                        let right_label = preview.right_label.clone();
                        let left_text = preview
                            .left_text
                            .clone()
                            .unwrap_or_else(|| tr(&language.get(), "（空）", "(empty)"));
                        let right_text = preview
                            .right_text
                            .clone()
                            .unwrap_or_else(|| tr(&language.get(), "（空）", "(empty)"));
                        let diff_rows = Arc::new(build_diff_rows(&left_text, &right_text));
                        view! {
                            <>
                                <Show when=move || note.is_some()>
                                    <div class="preview-note">{note_text.clone()}</div>
                                </Show>

                                <Show
                                    when=move || is_text
                                    fallback=move || {
                                        view! {
                                            <div class="binary-preview">
                                                <div class="empty-inline-title">{move || tr(&language.get(), "该文件不支持内嵌文本预览", "This file does not support inline text preview")}</div>
                                                <div class="empty-inline-copy">
                                                    {move || tr(&language.get(), "你可以点击右上角的按钮，把该历史版本文件导出到临时目录并交给系统默认程序打开。", "Use the button in the top-right corner to export this historical file to a temporary folder and open it with the system default app.")}
                                                </div>
                                            </div>
                                        }
                                    }
                                >
                                    <div class="diff-preview-shell">
                                        <div class="diff-preview-columns">
                                            <section class="diff-preview-column">
                                                <div class="text-preview-label">{left_label.clone()}</div>
                                                <div class="diff-preview-list">
                                                    <For
                                                        each={
                                                            let diff_rows = diff_rows.clone();
                                                            move || diff_rows.as_ref().clone().into_iter()
                                                        }
                                                        key=|row| format!(
                                                            "left-{}-{}-{}",
                                                            row.left_line.unwrap_or_default(),
                                                            row.right_line.unwrap_or_default(),
                                                            row.left_class,
                                                        )
                                                        children=move |row| view! {
                                                            <div class=row.left_class>
                                                                <span class="diff-line-no">
                                                                    {row.left_line.map(|value| value.to_string()).unwrap_or_default()}
                                                                </span>
                                                                <pre class="diff-content">{row.left_text}</pre>
                                                            </div>
                                                        }
                                                    />
                                                </div>
                                            </section>

                                            <section class="diff-preview-column">
                                                <div class="text-preview-label">{right_label.clone()}</div>
                                                <div class="diff-preview-list">
                                                    <For
                                                        each={
                                                            let diff_rows = diff_rows.clone();
                                                            move || diff_rows.as_ref().clone().into_iter()
                                                        }
                                                        key=|row| format!(
                                                            "right-{}-{}-{}",
                                                            row.left_line.unwrap_or_default(),
                                                            row.right_line.unwrap_or_default(),
                                                            row.right_class,
                                                        )
                                                        children=move |row| view! {
                                                            <div class=row.right_class>
                                                                <span class="diff-line-no">
                                                                    {row.right_line.map(|value| value.to_string()).unwrap_or_default()}
                                                                </span>
                                                                <pre class="diff-content">{row.right_text}</pre>
                                                            </div>
                                                        }
                                                    />
                                                </div>
                                            </section>
                                        </div>
                                    </div>
                                </Show>
                            </>
                        }.into_any()
                    }).unwrap_or_else(|| view! {
                        <div class="empty-inline">
                            <div class="empty-inline-title">{move || tr(&language.get(), "请选择一个文件", "Choose a file")}</div>
                            <div class="empty-inline-copy">{move || tr(&language.get(), "左侧点击变更文件后，这里会显示文本内容或二进制打开提示。", "After selecting a changed file on the left, its text preview or binary hint will appear here.")}</div>
                        </div>
                    }.into_any())
                }}
            </div>
        </section>
    }
}

#[component]
fn ComparePanel(
    versions: Vec<VersionEntry>,
    language: RwSignal<String>,
    compare_left: RwSignal<Option<i64>>,
    compare_right: RwSignal<Option<i64>>,
    on_compare: Callback<()>,
) -> impl IntoView {
    let versions = Arc::new(versions);
    view! {
        <section class="panel modal-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-label">{move || tr(&language.get(), "版本选择", "Version selection")}</div>
                    <div class="panel-title">{move || tr(&language.get(), "选择两个版本进行比较", "Choose two versions to compare")}</div>
                </div>
            </div>

            <div class="form-grid">
                <div class="field-block">
                    <label class="field-label">{move || tr(&language.get(), "基准版本", "Base version")}</label>
                    <select
                        class="select"
                        prop:value=move || compare_left.get().map(|value| value.to_string()).unwrap_or_default()
                        on:change=move |event| {
                            let target = event.target().unwrap().unchecked_into::<HtmlSelectElement>();
                            compare_left.set(parse_i64(target.value()));
                        }
                    >
                        <option value="">{move || tr(&language.get(), "请选择基准版本", "Choose a base version")}</option>
                        <For
                            each={
                                let versions = versions.clone();
                                move || versions.as_ref().clone().into_iter()
                            }
                            key=|version| version.id
                            children=move |version| view! {
                                <option value={version.id.to_string()}>
                                    {format!("{}  {}", version.version_number, version.description)}
                                </option>
                            }
                        />
                    </select>
                </div>

                <div class="field-block">
                    <label class="field-label">{move || tr(&language.get(), "目标版本", "Target version")}</label>
                    <select
                        class="select"
                        prop:value=move || compare_right.get().map(|value| value.to_string()).unwrap_or_default()
                        on:change=move |event| {
                            let target = event.target().unwrap().unchecked_into::<HtmlSelectElement>();
                            compare_right.set(parse_i64(target.value()));
                        }
                    >
                        <option value="">{move || tr(&language.get(), "请选择目标版本", "Choose a target version")}</option>
                        <For
                            each={
                                let versions = versions.clone();
                                move || versions.as_ref().clone().into_iter()
                            }
                            key=|version| version.id
                            children=move |version| view! {
                                <option value={version.id.to_string()}>
                                    {format!("{}  {}", version.version_number, version.description)}
                                </option>
                            }
                        />
                    </select>
                </div>

                <div class="field-block">
                    <label class="field-label">{move || tr(&language.get(), "操作", "Action")}</label>
                    <button
                        class="primary-button fill-button"
                        on:click=move |_| on_compare.run(())
                        disabled=move || compare_left.get().is_none() || compare_right.get().is_none()
                    >
                        {move || tr(&language.get(), "开始比较", "Start comparison")}
                    </button>
                </div>
            </div>
        </section>
    }
}

#[component]
fn IgnoreRulesPanel(
    draft: RwSignal<String>,
    language: RwSignal<String>,
    on_save: Callback<()>,
) -> impl IntoView {
    view! {
        <section class="panel modal-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-label">{move || tr(&language.get(), "扫描设置", "Scan settings")}</div>
                    <div class="panel-title">{move || tr(&language.get(), "编辑 .vermanignore", "Edit .vermanignore")}</div>
                </div>
            </div>

            <div class="field-note">
                {move || tr(&language.get(), "每行一个模式，例如 `target/`、`node_modules/`、`*.log`。", "One pattern per line, for example `target/`, `node_modules/`, or `*.log`.")}
            </div>

            <textarea
                class="textarea ignore-editor"
                prop:value=move || draft.get()
                on:input=move |event| {
                    let target = event.target().unwrap().unchecked_into::<HtmlTextAreaElement>();
                    draft.set(target.value());
                }
            />

            <div class="modal-actions">
                <button class="primary-button" on:click=move |_| on_save.run(())>
                    {move || tr(&language.get(), "保存规则", "Save rules")}
                </button>
            </div>
        </section>
    }
}

#[component]
fn LanguagePanel(language: RwSignal<String>, on_change: Callback<String>) -> impl IntoView {
    view! {
        <section class="panel modal-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-label">{move || tr(&language.get(), "界面语言", "Interface language")}</div>
                    <div class="panel-title">{move || tr(&language.get(), "选择你希望使用的语言", "Choose the language you want to use")}</div>
                </div>
            </div>

            <div class="field-note">
                {move || tr(&language.get(), "语言设置会保存到本地，重新打开应用后仍然生效。", "The selected language is stored locally and will be reused the next time you open the app.")}
            </div>

            <div class="modal-actions">
                <button
                    class=move || {
                        if language.get() == "zh" {
                            "primary-button"
                        } else {
                            "secondary-button"
                        }
                    }
                    on:click=move |_| on_change.run("zh".to_string())
                >
                    "中文"
                </button>
                <button
                    class=move || {
                        if language.get() == "en" {
                            "primary-button"
                        } else {
                            "secondary-button"
                        }
                    }
                    on:click=move |_| on_change.run("en".to_string())
                >
                    "English"
                </button>
            </div>
        </section>
    }
}

#[component]
fn IntegrationPanel(
    status: RwSignal<Option<ContextMenuStatus>>,
    language: RwSignal<String>,
    on_install: Callback<()>,
    on_uninstall: Callback<()>,
) -> impl IntoView {
    view! {
        <section class="panel modal-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-label">{move || tr(&language.get(), "资源管理器集成", "Explorer integration")}</div>
                    <div class="panel-title">{move || tr(&language.get(), "管理 Windows 右键菜单", "Manage the Windows context menu")}</div>
                </div>
            </div>

            {move || {
                status.get().map(|status| {
                    view! {
                        <div class="integration-card">
                            <div class="integration-status">
                                <span class=if status.installed { "state-dot state-on" } else { "state-dot" }></span>
                                <span>{if status.installed { tr(&language.get(), "已安装", "Installed") } else { tr(&language.get(), "未安装", "Not installed") }}</span>
                            </div>
                            <div class="field-note">{status.detail}</div>
                            <div class="path-box">
                                {status.command_path.unwrap_or_else(|| tr(&language.get(), "当前还没有可用的可执行路径信息", "No executable path information is available yet"))}
                            </div>
                        </div>
                    }
                        .into_any()
                }).unwrap_or_else(|| view! { <div class="field-note">{move || tr(&language.get(), "正在读取当前状态...", "Reading current status...")}</div> }.into_any())
            }}

            <div class="modal-actions">
                <button class="primary-button" on:click=move |_| on_install.run(())>
                    {move || tr(&language.get(), "安装右键菜单", "Install context menu")}
                </button>
                <button class="secondary-button" on:click=move |_| on_uninstall.run(())>
                    {move || tr(&language.get(), "卸载右键菜单", "Uninstall context menu")}
                </button>
            </div>
        </section>
    }
}

#[component]
fn DiffRow(entry: VersionDiffEntry, language: RwSignal<String>) -> impl IntoView {
    let status_class_name = status_class(&entry.status);
    let status_label = entry.status.clone();
    view! {
        <article class="list-row diff-row">
            <div class=status_class_name>{move || status_text(&status_label, &language.get())}</div>
            <div class="row-main">
                <div class="row-title">{entry.relative_path}</div>
                <div class="row-meta">
                    {format!(
                        "{} -> {}",
                        entry.left_size.map(format_size).unwrap_or_else(|| tr(&language.get(), "无", "N/A")),
                        entry.right_size.map(format_size).unwrap_or_else(|| tr(&language.get(), "无", "N/A")),
                    )}
                </div>
            </div>
            <div class="hash-stack">
                <span>{entry.left_hash.unwrap_or_else(|| "-".to_string())}</span>
                <span>{entry.right_hash.unwrap_or_else(|| "-".to_string())}</span>
            </div>
        </article>
    }
}

#[component]
fn DiffPanel(
    result: RwSignal<Option<VersionDiffResult>>,
    language: RwSignal<String>,
) -> impl IntoView {
    view! {
        <section class="panel modal-panel diff-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-label">{move || tr(&language.get(), "比较结果", "Comparison result")}</div>
                    <div class="panel-title">{move || tr(&language.get(), "文件差异列表", "File difference list")}</div>
                </div>
                {move || {
                    result.get().map(|diff| {
                        view! {
                            <div class="diff-summary">
                                <span class="status-chip status-add">{move || format!("{} {}", tr(&language.get(), "新增", "Added"), diff.added)}</span>
                                <span class="status-chip status-modify">{move || format!("{} {}", tr(&language.get(), "修改", "Modified"), diff.modified)}</span>
                                <span class="status-chip status-delete">{move || format!("{} {}", tr(&language.get(), "删除", "Deleted"), diff.deleted)}</span>
                            </div>
                        }.into_any()
                    }).unwrap_or_else(|| view! { <div class="panel-badge">{move || tr(&language.get(), "尚未比较", "Not compared yet")}</div> }.into_any())
                }}
            </div>

            {move || {
                result.get().map(|diff| {
                    view! {
                        <>
                            <div class="compare-banner">
                                <span class="panel-badge">{diff.left_version_label}</span>
                                <span class="compare-arrow">"→"</span>
                                <span class="panel-badge">{diff.right_version_label}</span>
                            </div>

                            <div class="list-shell">
                                <For
                                    each=move || diff.entries.clone().into_iter()
                                    key=|entry| format!("{}-{}", entry.status, entry.relative_path)
                                    children=move |entry| view! { <DiffRow entry=entry language=language /> }
                                />
                            </div>
                        </>
                    }.into_any()
                }).unwrap_or_else(|| view! {
                    <div class="empty-inline">
                        <div class="empty-inline-title">{move || tr(&language.get(), "还没有对比结果", "No comparison result yet")}</div>
                        <div class="empty-inline-copy">{move || tr(&language.get(), "选择两个版本后点击“开始比较”，结果会显示在这里。", "Choose two versions and click “Start comparison”; the result will appear here.")}</div>
                    </div>
                }.into_any())
            }}
        </section>
    }
}

#[derive(Clone)]
struct PreviewDiffRow {
    left_line: Option<usize>,
    right_line: Option<usize>,
    left_text: String,
    right_text: String,
    left_class: &'static str,
    right_class: &'static str,
}

fn build_diff_rows(left: &str, right: &str) -> Vec<PreviewDiffRow> {
    let diff = TextDiff::from_lines(left, right);
    let mut rows = Vec::new();
    let mut left_line = 1usize;
    let mut right_line = 1usize;
    let mut delete_buffer: Vec<(usize, String)> = Vec::new();
    let mut insert_buffer: Vec<(usize, String)> = Vec::new();

    let flush_buffers = |rows: &mut Vec<PreviewDiffRow>,
                         delete_buffer: &mut Vec<(usize, String)>,
                         insert_buffer: &mut Vec<(usize, String)>| {
        let max_len = delete_buffer.len().max(insert_buffer.len());
        for index in 0..max_len {
            let left_entry = delete_buffer.get(index).cloned();
            let right_entry = insert_buffer.get(index).cloned();
            let has_left = left_entry.is_some();
            let has_right = right_entry.is_some();
            rows.push(PreviewDiffRow {
                left_line: left_entry.as_ref().map(|(line, _)| *line),
                right_line: right_entry.as_ref().map(|(line, _)| *line),
                left_text: left_entry
                    .as_ref()
                    .map(|(_, text)| text.clone())
                    .unwrap_or_else(|| " ".to_string()),
                right_text: right_entry
                    .as_ref()
                    .map(|(_, text)| text.clone())
                    .unwrap_or_else(|| " ".to_string()),
                left_class: if has_left {
                    "diff-cell diff-cell-delete"
                } else {
                    "diff-cell diff-cell-empty"
                },
                right_class: if has_right {
                    "diff-cell diff-cell-add"
                } else {
                    "diff-cell diff-cell-empty"
                },
            });
        }
        delete_buffer.clear();
        insert_buffer.clear();
    };

    for change in diff.iter_all_changes() {
        let text = normalize_diff_text(change.to_string());
        match change.tag() {
            ChangeTag::Equal => {
                flush_buffers(&mut rows, &mut delete_buffer, &mut insert_buffer);
                rows.push(PreviewDiffRow {
                    left_line: Some(left_line),
                    right_line: Some(right_line),
                    left_text: text.clone(),
                    right_text: text,
                    left_class: "diff-cell diff-cell-equal",
                    right_class: "diff-cell diff-cell-equal",
                });
                left_line += 1;
                right_line += 1;
            }
            ChangeTag::Delete => {
                delete_buffer.push((left_line, text));
                left_line += 1;
            }
            ChangeTag::Insert => {
                insert_buffer.push((right_line, text));
                right_line += 1;
            }
        }
    }

    flush_buffers(&mut rows, &mut delete_buffer, &mut insert_buffer);

    if rows.is_empty() {
        rows.push(PreviewDiffRow {
            left_line: Some(1),
            right_line: Some(1),
            left_text: "（空）".to_string(),
            right_text: "（空）".to_string(),
            left_class: "diff-cell diff-cell-empty",
            right_class: "diff-cell diff-cell-empty",
        });
    }

    rows
}

fn normalize_diff_text(text: String) -> String {
    let normalized = text.replace('\r', "").trim_end_matches('\n').to_string();
    if normalized.is_empty() {
        " ".to_string()
    } else {
        normalized
    }
}

fn is_generic_preview_note(note: &str) -> bool {
    let normalized = note.trim();
    normalized.contains("左右两侧分别是上一版本与当前版本的文本内容")
        || normalized.contains("previous and current version")
}

fn tr(language: &str, zh: &str, en: &str) -> String {
    if language == "en" {
        en.to_string()
    } else {
        zh.to_string()
    }
}

fn format_count<T>(value: T, language: &str, zh_unit: &str, en_unit: &str) -> String
where
    T: std::fmt::Display,
{
    if language == "en" {
        format!("{value} {en_unit}")
    } else {
        format!("{value} {zh_unit}")
    }
}

fn parse_i64(value: String) -> Option<i64> {
    if value.trim().is_empty() {
        None
    } else {
        value.parse().ok()
    }
}

fn status_text(status: &str, language: &str) -> String {
    match status {
        "add" => tr(language, "新增", "Added"),
        "modify" => tr(language, "修改", "Modified"),
        "delete" => tr(language, "删除", "Deleted"),
        _ => tr(language, "变更", "Changed"),
    }
}

fn status_class(status: &str) -> &'static str {
    match status {
        "add" => "status-chip status-add",
        "modify" => "status-chip status-modify",
        "delete" => "status-chip status-delete",
        _ => "status-chip",
    }
}

fn format_size(size: u64) -> String {
    const KB: f64 = 1024.0;
    const MB: f64 = KB * 1024.0;

    if size == 0 {
        "0 B".to_string()
    } else if size as f64 >= MB {
        format!("{:.1} MB", size as f64 / MB)
    } else if size as f64 >= KB {
        format!("{:.1} KB", size as f64 / KB)
    } else {
        format!("{size} B")
    }
}
