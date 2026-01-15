"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
const tl = require("azure-pipelines-task-lib/task");
const tr = require("azure-pipelines-task-lib/toolrunner");

function run() {
    return __awaiter(this, void 0, void 0, function* () {
        try {
            // Get inputs
            const command = tl.getInput('command', true) || 'hydrate';
            const authType = tl.getInput('authType', true) || 'servicePrincipal';
            const workspaceId = tl.getInput('workspaceId', false);
            const lakehouseId = tl.getInput('lakehouseId', false);
            const configPath = tl.getPathInput('configPath', false);
            const sourcePath = tl.getInput('sourcePath', false);
            const outputPath = tl.getPathInput('outputPath', false) || './metadata';
            const outputFormat = tl.getInput('outputFormat', false) || 'yaml';
            const dryRun = tl.getBoolInput('dryRun', false);
            const verbose = tl.getBoolInput('verbose', false);
            const pythonVersion = tl.getInput('pythonVersion', false) || '3.11';

            // Set up authentication environment variables
            if (authType === 'servicePrincipal') {
                const tenantId = tl.getInput('tenantId', false);
                const clientId = tl.getInput('clientId', false);
                const clientSecret = tl.getInput('clientSecret', false);
                const azureSubscription = tl.getInput('azureSubscription', false);

                if (azureSubscription) {
                    // Get credentials from service connection
                    const connectedService = tl.getInput('azureSubscription', false);
                    if (connectedService) {
                        const servicePrincipalId = tl.getEndpointAuthorizationParameter(connectedService, 'serviceprincipalid', true);
                        const servicePrincipalKey = tl.getEndpointAuthorizationParameter(connectedService, 'serviceprincipalkey', true);
                        const tenantIdFromConn = tl.getEndpointAuthorizationParameter(connectedService, 'tenantid', true);
                        
                        if (servicePrincipalId) process.env['AZURE_CLIENT_ID'] = servicePrincipalId;
                        if (servicePrincipalKey) process.env['AZURE_CLIENT_SECRET'] = servicePrincipalKey;
                        if (tenantIdFromConn) process.env['AZURE_TENANT_ID'] = tenantIdFromConn;
                    }
                } else {
                    // Use explicit credentials
                    if (tenantId) process.env['AZURE_TENANT_ID'] = tenantId;
                    if (clientId) process.env['AZURE_CLIENT_ID'] = clientId;
                    if (clientSecret) process.env['AZURE_CLIENT_SECRET'] = clientSecret;
                }
            }

            // Set Fabric environment variables
            if (workspaceId) process.env['FABRIC_WORKSPACE_ID'] = workspaceId;
            if (lakehouseId) process.env['FABRIC_LAKEHOUSE_ID'] = lakehouseId;

            // Find Python
            const pythonPath = tl.which('python', true);
            console.log(`Using Python: ${pythonPath}`);

            // Install fabric-hydrate
            console.log('Installing fabric-hydrate...');
            const pipInstall = tl.tool(pythonPath)
                .arg('-m')
                .arg('pip')
                .arg('install')
                .arg('fabric-hydrate')
                .arg('--quiet');
            
            const pipResult = yield pipInstall.exec();
            if (pipResult !== 0) {
                throw new Error('Failed to install fabric-hydrate');
            }

            // Build command arguments
            const args = ['-m', 'fabric_hydrate.cli', command];

            if (command === 'hydrate') {
                if (configPath && tl.exist(configPath)) {
                    args.push('--config', configPath);
                } else if (sourcePath) {
                    args.push('--source', sourcePath);
                }
                args.push('--output', outputPath);
                args.push('--format', outputFormat);
                if (dryRun) args.push('--dry-run');
            } else if (command === 'diff') {
                if (sourcePath) args.push(sourcePath);
                if (workspaceId) args.push('--workspace-id', workspaceId);
                if (lakehouseId) args.push('--lakehouse-id', lakehouseId);
            } else if (command === 'validate') {
                if (configPath) args.push(configPath);
            } else if (command === 'schema') {
                if (sourcePath) args.push(sourcePath);
                args.push('--format', outputFormat);
            }

            if (verbose) args.push('--verbose');

            // Run fabric-hydrate
            console.log(`Running: python ${args.join(' ')}`);
            const fabricHydrate = tl.tool(pythonPath).arg(args);
            
            const execResult = yield fabricHydrate.exec();
            
            if (execResult !== 0) {
                throw new Error(`fabric-hydrate ${command} failed with exit code ${execResult}`);
            }

            // Set output variables
            tl.setVariable('MetadataPath', outputPath);
            
            // Check for changes
            if (tl.exist(outputPath)) {
                const files = tl.findMatch(outputPath, '**/*');
                tl.setVariable('HasChanges', files.length > 0 ? 'true' : 'false');
            } else {
                tl.setVariable('HasChanges', 'false');
            }

            console.log('Task completed successfully');
            tl.setResult(tl.TaskResult.Succeeded, 'fabric-hydrate completed successfully');

        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : String(err);
            tl.setResult(tl.TaskResult.Failed, errorMessage);
        }
    });
}

run();
