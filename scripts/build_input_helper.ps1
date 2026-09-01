[CmdletBinding()]
param(
    [switch]$TestOnly,
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "..\bin"
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$nativeDirectory = Join-Path $repositoryRoot "native\input-helper"
$sourceFile = Join-Path $nativeDirectory "input_helper.c"
$testSourceFile = Join-Path $nativeDirectory "input_helper_test.c"

function Resolve-VcVarsAll {
    $candidates = [System.Collections.Generic.List[string]]::new()
    $configuredPath = [Environment]::GetEnvironmentVariable("TRAINER_RELAY_VCVARSALL")
    if ($configuredPath) {
        [void]$candidates.Add($configuredPath)
    }

    $vswhereCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"),
        (Join-Path $env:ProgramFiles "Microsoft Visual Studio\Installer\vswhere.exe")
    )
    foreach ($vswhere in $vswhereCandidates) {
        if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
            $installationPath = & $vswhere -latest -products '*' -property installationPath 2>$null | Select-Object -First 1
            if ($installationPath) {
                [void]$candidates.Add((Join-Path $installationPath.Trim() "VC\Auxiliary\Build\vcvarsall.bat"))
            }
        }
    }

    $directRoots = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio"),
        (Join-Path $env:ProgramFiles "Microsoft Visual Studio")
    ) | Where-Object { $_ }
    foreach ($root in $directRoots) {
        if (Test-Path -LiteralPath $root -PathType Container) {
            $directMatches = Get-ChildItem -LiteralPath $root -Filter "vcvarsall.bat" -File -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match "\\VC\\Auxiliary\\Build\\vcvarsall\.bat$" } |
                Sort-Object FullName
            foreach ($match in $directMatches) {
                [void]$candidates.Add($match.FullName)
            }
        }
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "MSVC vcvarsall.bat was not found. Install the C++ build tools or set TRAINER_RELAY_VCVARSALL."
}

function Invoke-Msvc {
    param(
        [Parameter(Mandatory = $true)][string]$VcVarsAll,
        [Parameter(Mandatory = $true)][string]$TargetArchitecture,
        [Parameter(Mandatory = $true)][string]$OutputFile,
        [switch]$BuildTest
    )

    $arguments = @(
        "/nologo", "/TC", "/W4", "/WX", "/O1", "/GS", "/MT",
        "/I", ('"{0}"' -f $nativeDirectory)
    )
    if ($BuildTest) {
        $arguments += "/DINPUT_HELPER_TEST"
        $arguments += ('"{0}"' -f $sourceFile)
        $arguments += ('"{0}"' -f $testSourceFile)
    } else {
        $arguments += ('"{0}"' -f $sourceFile)
    }
    $objectDirectory = Join-Path $buildDirectory "$TargetArchitecture-$(if ($BuildTest) { 'test' } else { 'helper' })"
    New-Item -ItemType Directory -Force -Path $objectDirectory | Out-Null
    $machine = if ($TargetArchitecture -eq "x86") { "X86" } else { "X64" }
    $arguments += ('/Fe:"{0}"' -f $OutputFile)
    $arguments += @("/link", "/Brepro", "/DYNAMICBASE", "/NXCOMPAT", "/SUBSYSTEM:CONSOLE", "/MACHINE:$machine")
    $compileCommand = "cd /d `"$objectDirectory`" && call `"$VcVarsAll`" $TargetArchitecture && cl.exe $($arguments -join ' ')"

    & $env:ComSpec /d /s /c $compileCommand
    if ($LASTEXITCODE -ne 0) {
        throw "MSVC failed for $TargetArchitecture with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf) -or
    -not (Test-Path -LiteralPath $testSourceFile -PathType Leaf)) {
    throw "Input helper sources are missing under $nativeDirectory."
}

$vcVarsAll = Resolve-VcVarsAll
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$outputDirectoryPath = (Resolve-Path -LiteralPath $OutputDirectory).Path
$processId = [System.Diagnostics.Process]::GetCurrentProcess().Id
$buildDirectory = Join-Path ([IO.Path]::GetTempPath()) "TrainerRelay.InputHelper.$processId"
$testOutputs = @{
    x86 = Join-Path ([IO.Path]::GetTempPath()) "TrainerRelay.InputHelper.test.x86.$processId.exe"
    x64 = Join-Path ([IO.Path]::GetTempPath()) "TrainerRelay.InputHelper.test.x64.$processId.exe"
}

try {
    foreach ($testArchitecture in @("x86", "amd64")) {
        $testLabel = if ($testArchitecture -eq "x86") { "x86" } else { "x64" }
        $testOutput = $testOutputs[$testLabel]
        Invoke-Msvc -VcVarsAll $vcVarsAll -TargetArchitecture $testArchitecture -OutputFile $testOutput -BuildTest
        & $testOutput
        if ($LASTEXITCODE -ne 0) {
            throw "Input helper host tests failed for $testLabel with exit code $LASTEXITCODE."
        }
    }

    if ($TestOnly) {
        Write-Output "Input helper host tests passed."
    } else {
        $x86Output = Join-Path $outputDirectoryPath "TrainerRelay.InputHelper.x86.exe"
        $x64Output = Join-Path $outputDirectoryPath "TrainerRelay.InputHelper.x64.exe"
        Invoke-Msvc -VcVarsAll $vcVarsAll -TargetArchitecture "x86" -OutputFile $x86Output
        Invoke-Msvc -VcVarsAll $vcVarsAll -TargetArchitecture "amd64" -OutputFile $x64Output

        $manifestScript = Join-Path $repositoryRoot "scripts\generate_helper_manifest.py"
        & python $manifestScript --input-dir $outputDirectoryPath --output (Join-Path $outputDirectoryPath "input-helper-manifest.json")
        if ($LASTEXITCODE -ne 0) {
            throw "Input helper manifest generation failed with exit code $LASTEXITCODE."
        }
        Write-Output "Built x86 and x64 input helpers in $outputDirectoryPath."
    }
}
finally {
    foreach ($testOutput in $testOutputs.Values) {
        Remove-Item -LiteralPath $testOutput -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $buildDirectory -Recurse -Force -ErrorAction SilentlyContinue
}
