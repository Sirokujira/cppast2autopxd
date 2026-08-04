rem cmake にパスを通していない場合の対応
rem rem (cmake のモジュールを zip で落としてきた場合は環境変数を設定して対応する/もしくは msi でのインストール時に環境変数の設定を行っていない場合も同様に対応すること)
rem rem 変更部分
rem % set CMAKE_BIN_PATH=%INSTALL_DIR%
rem set LLVM_DIR=%INSTALL_DIR%/lib/llvm
rem set PATH=%CMAKE_BIN_PATH%;%LLVM_DIR%/bin;%PATH%
rem rem set CPPAST_ROOT=%INSTALL_DIR%/lib/install/cppast
rem set cppast_DIR=%INSTALL_DIR%/lib/install/cppast
rem set cppast_ROOT=%INSTALL_DIR%/lib/install/cppast
rem rem extern?
rem rem set type_safe_DIR=%INSTALL_DIR%/lib/install/type_safe
rem rem set type_safe_ROOT=%INSTALL_DIR%/lib/install/type_safe
rem rem extern
rem set cxxopts_DIR=%INSTALL_DIR%/lib/install/cxxopts
rem set cxxopts_ROOT=%INSTALL_DIR%/lib/install/cxxopts
