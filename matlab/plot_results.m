function plot_results(root)
% Audited scientific plots. Base MATLAB only; no Statistics Toolbox.
if nargin<1, root=fullfile('results','release_20261113'); end
root=char(root); fd=fullfile(root,'figures');
if ~exist(fd,'dir'), mkdir(fd); end
set(groot,'defaultAxesFontName','Arial','defaultAxesFontSize',10, ...
 'defaultTextInterpreter','none','defaultLegendInterpreter','none', ...
 'defaultAxesTickLabelInterpreter','none');
styles={'-','--',':','-.'};

% Event times are irregular and duplicated at jumps. Use post-jump states.
f=load(fullfile(root,'S2_once','fields.mat'));
[ut,last]=unique(f.t(:),'last'); tq=linspace(0,15,1501)';
displayWidth=interp1(ut,max(f.w(last,:),0),tq,'previous');
fig=nf(950,500);imagesc(f.x/1000,tq,displayWidth);axis xy;
c=colorbar;c.Label.String='Effective beach width (m)';colormap(fig,parula);
xlabel('Alongshore coordinate (km)');ylabel('Time (yr after 2027)');
title('MODEL | S2 once: effective beach width');
xline(-2.5,'w:','LineWidth',1.5);xline(2.5,'w:','LineWidth',1.5);
saveplots(fig,fd,'F1_S2_width_heatmap');

fig=nf(950,600);tiledlayout(2,1,'TileSpacing','compact');
names={'S1_uniform','S1_hotspot','S1_multi'};
layoutLabels={'Uniform (5 km)','Hotspot (1 km)','Five segments (0.5 km each)'};
for tile=1:2
 nexttile;hold on;
 for k=1:3
  g=load(fullfile(root,names{k},'fields.mat'));central=abs(g.x)<2500;
  if tile==1,idx=find(g.t>=5,1);else,idx=length(g.t);end
  plot(g.x(central)/1000,max(g.w(idx,central),0),styles{k},'Color',[.1 .1 .1],'LineWidth',1.7,'DisplayName',layoutLabels{k});
 end
 yline(20,'k-.','DisplayName','Width threshold');xlabel('Alongshore coordinate (km)');
 ylabel('Effective beach width (m)');title(sprintf('MODEL | equal-volume layouts: year %d',5+10*(tile-1)));
 limits=ylim;ylim([min(18,limits(1)),limits(2)]); % Keep 20 m threshold visible above the axis.
 legend('Location','best','NumColumns',2);grid on;
end
saveplots(fig,fd,'F2_layout_profiles');

T=readtable(fullfile(root,'summary.csv'),'TextType','string');
fig=nf(1100,650);tiledlayout(2,1,'TileSpacing','compact');
for si=1:2
 s="S"+string(si+1);names=[s+"_baseline",s+"_once",s+"_repeat",s+"_targeted",s+"_adaptive"];
 [found,indices]=ismember(names,T.run);S=T(indices(found),:);
 nexttile;bars=bar(1:height(S),[S.E_b_myr,S.E_w_myr]);
 bars(1).FaceColor=[.25 .25 .25];bars(2).FaceColor=[.75 .75 .75];xticks(1:height(S));
 xticklabels({'Baseline','Once','Repeat','Triggered hotspot','Ensemble adaptive'});
 ylabel('Risk exposure (m yr)');title("MODEL | "+s+": seed 42, local sand");
 legend({'Building-clearance exposure','Beach-width exposure'},'Location','best');grid on;
end
saveplots(fig,fd,'F3_strategy_exposure');

fig=nf(1100,700);tiledlayout(2,2,'TileSpacing','compact');nexttile;hold on;
strategies={'once','repeat','targeted','adaptive'};q=zeros(4,3);
for k=1:4
 M=readtable(fullfile(root,['MC_S2_' strategies{k}],'runs.csv'));q(k,:)=qb(M.E_b,[.1,.5,.9]);
end
errorbar(1:3,q(1:3,2),q(1:3,2)-q(1:3,1),q(1:3,3)-q(1:3,2),'ko','MarkerFaceColor',[.25 .25 .25],'LineWidth',1.6);
xticks(1:3);xticklabels({'Once','Repeat','Triggered hotspot'});xlim([.5,3.5]);
ylabel('Building-clearance exposure (m yr)');grid on;
title('MODEL | S2 active policies: median, p10-p90');
nexttile;M=readtable(fullfile(root,'MC_S2_none','runs.csv'));ref=[qb(M.E_b,[.1,.5,.9]);q(4,:)];
errorbar(1:2,ref(:,2),ref(:,2)-ref(:,1),ref(:,3)-ref(:,2),'ko','MarkerFaceColor',[.25 .25 .25],'LineWidth',1.6);
xticks(1:2);xticklabels({'Baseline','Ensemble adaptive'});xlim([.5,2.5]);
ylabel('Building-clearance exposure (m yr)');title('MODEL | same seeds, reference policies');grid on;
nexttile([1,2]);hold on;J=jsondecode(fileread(fullfile(root,'MC_S2_once','summary.json')));
x=J.width_end.x(:)/1000;lo=max(J.width_end.p10(:),0);hi=max(J.width_end.p90(:),0);
fill([x;flipud(x)],[lo;flipud(hi)],[.83 .83 .83],'EdgeColor','none','DisplayName','Pointwise p10-p90');
plot(x,max(J.width_end.p50,0),'k-','LineWidth',1.6,'DisplayName','Pointwise median');
yline(20,'k--','DisplayName','Width threshold');xlim([-2.5,2.5]);
xlabel('Alongshore coordinate (km)');ylabel('Effective final width (m)');
title('MODEL | S2 once: final width; storm uncertainty, fixed parameters');legend('Location','best');grid on;
limits=ylim;ylim([min(0,limits(1)),max(22,limits(2))]);
saveplots(fig,fd,'F4_MC_S2_uncertainty');

% Average matched storm seeds at each parameter value before comparing range.
O=readtable(fullfile(root,'OAT_S2_once','oat.csv'),'TextType','string');
names=unique(O.parameter,'stable');spread=zeros(length(names),1);
for k=1:length(names)
 S=O(O.parameter==names(k),:);vs=unique(S.value);means=zeros(size(vs));
 for j=1:length(vs),means(j)=mean(S.E_b(S.value==vs(j)));end
 spread(k)=max(means)-min(means);
end
[spread,order]=sort(spread,'ascend');fig=nf(950,650);
barh(1:length(names),spread,'FaceColor',[.35 .35 .35]);yticks(1:length(names));yticklabels(names(order));
xlabel('Range of seed-mean building exposure (m yr)');title('MODEL | OAT response range; input ranges differ');grid on;
saveplots(fig,fd,'F5_OAT_sensitivity');

% Repeated times draw vertical jumps; trajectories do not interpolate across storms.
fig=nf(1000,650);tiledlayout(2,1,'TileSpacing','compact');
names={'S2_baseline','S2_once','S2_repeat','S2_targeted'};
policyLabels={'Baseline','Once','Repeat','Triggered hotspot'};
for tile=1:2
 nexttile;hold on;
 for k=1:4
  g=load(fullfile(root,names{k},'fields.mat'));central=abs(g.x)<2500;
  if tile==1,vals=mean(max(g.w(:,central),0),2);else,vals=mean(25+g.y(:,central),2);end
  plot(g.t,vals,styles{k},'Color',[.1 .1 .1],'LineWidth',1.4,'DisplayName',policyLabels{k});
 end
 if tile==1,yline(20,'k-.','HandleVisibility','off');ylabel('Mean effective beach width (m)');
 else,yline(5,'k-.','HandleVisibility','off');ylabel('Mean building clearance (m)');end
 xlabel('Time (yr after 2027)');legend('Location','best','NumColumns',2);grid on;
end
sgtitle('MODEL | S2 width and building-clearance trajectories','Color','k');saveplots(fig,fd,'F6_S2_trajectories');

L=readtable(fullfile(root,'S2_once','ledger.csv'));fig=nf(1000,650);tiledlayout(2,1,'TileSpacing','compact');
nexttile;stock=L.V_domain+L.O_domain;
reconstructed=stock-stock(1)+L.flux_outer_left_cum+L.flux_outer_right_cum+ ...
 L.offshore_loss_cum+L.chronic_loss_cum-(L.R_c_cum-L.R_c_cum(1));
plot(L.t,L.placed_cum/1e6,'k-',L.t,reconstructed/1e6,'--','LineWidth',1.5);
xlabel('Time (yr)');ylabel('Sand volume (million m^3)');
legend({'Placed','Reconstructed from ledger'},'Location','best');grid on;
title('MODEL | full-domain budget, including current deficit correction');
nexttile;semilogy(L.t,max(L.residual_rel,eps),'k-',L.t,max(L.residual_central_rel,eps),'k--','LineWidth',1.2);
yline(1e-6,'k:','Acceptance threshold');xlabel('Time (yr)');ylabel('Relative balance residual');
legend({'Full 9 km','Central 5 km'},'Location','best');grid on;
saveplots(fig,fd,'F7_sand_accounting');

R=readtable(fullfile(root,'timing','runs.csv'),'TextType','string');fig=nf(1000,650);
tiledlayout(2,1,'TileSpacing','compact');labels={'early','spread','late'};
for tile=1:2
 nexttile;hold on;q=zeros(3,3);
 if tile==1,vals=R.E_b;label='Building-clearance exposure (m yr)';
 else,vals=R.E_w;label='Beach-width exposure (m yr)';end
 for k=1:3,q(k,:)=qb(vals(R.timing==labels{k}),[.1,.5,.9]);end
 errorbar(1:3,q(:,2),q(:,2)-q(:,1),q(:,3)-q(:,2),'ko','MarkerFaceColor',[.25 .25 .25],'LineWidth',1.5);
 xticks(1:3);xticklabels({'Early (0-5 yr)','Spread (0-15 yr)','Late (10-15 yr)'});ylabel(label);grid on;
 xlim([.5,3.5]);
end
sgtitle('MODEL | same six storm marks: median and p10-p90','Color','k');
saveplots(fig,fd,'F8_storm_timing');

P=readtable(fullfile(root,'phase_map.csv'));fig=nf(950,500);hold on;
feasible=P.uniform_initially_feasible;
if ~isnumeric(feasible) && ~islogical(feasible),feasible=strcmpi(string(feasible),"true");end
scatter(P.w_min_m,P.volume_m3/1e6,18,double(feasible),'filled');
colormap(fig,[.80 .80 .80;.25 .25 .25]);clim([0,1]);
xs=linspace(10,25,300);plot(xs,10*5000*max(20-xs,0)/1e6,'k-','LineWidth',1.8);
xlabel('Minimum initial width (m)');ylabel('Placed sand (million m^3)');
title('ANALYTIC | uniform placement: instantaneous coverage feasibility');
subtitle('Dark = all locations initially meet 20 m; no durability claim');grid on;
yticks(0:.2:1);xticks(10:3:25);
saveplots(fig,fd,'F9_initial_feasibility');

H=readtable(fullfile(root,'history','selected_transects.csv'));fig=nf(1000,750);tiledlayout(2,1,'TileSpacing','compact');nexttile;hold on;
histogram(H.LRR78_2002,20,'DisplayStyle','stairs','EdgeColor','k','LineWidth',1.6,'DisplayName','OBS: 1978-2002');
histogram(H.LRR89_2002,20,'DisplayStyle','stairs','LineStyle','--','EdgeColor','k','LineWidth',1.6,'DisplayName','OBS: 1989-2002');
xlabel('Historical shoreline change rate (m/yr; negative = erosion)');ylabel('Transects');
title('OBS | fixed historical northing window; overlapping periods');legend('Location','best');grid on;
nexttile;R=readtable(fullfile(root,'history','holdout_predictions.csv'));
scatter(R.heldout_retreat_myr,R.predicted_retreat_myr,20,'k','filled');hold on;
limits=[min([R.heldout_retreat_myr;R.predicted_retreat_myr]),max([R.heldout_retreat_myr;R.predicted_retreat_myr])];
plot(limits,limits,'k--','LineWidth',1.3);xlim(limits);ylim(limits);
xlabel('OBS | 1989-2002 retreat rate (m/yr)');ylabel('MODEL | predicted retreat rate (m/yr)');
title('Rate-field temporal holdout: trained on 1978-1989; shared 1989 boundary');grid on;
saveplots(fig,fd,'F10_history_diagnostic');

fig=nf(1100,600);tiledlayout(1,2,'TileSpacing','compact');groups={'transport','storm'};
for gi=1:2
 G=readtable(fullfile(root,['GLOBAL_' groups{gi}],'indices.csv'),'TextType','string');
 G=G(G.output=="local_once_E_b" & G.order~="second",:);
 keys=unique(G.parameter,'stable');values=zeros(length(keys),2);
 for k=1:length(keys)
  values(k,1)=G.index(G.parameter==keys(k) & G.order=="first");
  values(k,2)=G.index(G.parameter==keys(k) & G.order=="total");
 end
 nexttile;bars=bar(1:length(keys),values);bars(1).FaceColor=[.25 .25 .25];bars(2).FaceColor=[.75 .75 .75];
 xticks(1:length(keys));xticklabels(keys);
 ylabel('Sobol index estimate');title(['MODEL | ' groups{gi} '; see convergence table']);
 legend({'First order','Total order'},'Location','best');grid on;
end
sgtitle('N=512; independent uniform inputs; two storm seeds; replicated diagnostics','Color','k');
saveplots(fig,fd,'F11_exploratory_global_sensitivity');

J=jsondecode(fileread(fullfile(root,'S1_hotspot','results.json')));
A=J.sand_attribution.fraction_of_total_placed;keys=fieldnames(A);values=zeros(length(keys),1);
for k=1:length(keys),values(k)=A.(keys{k});end
fig=nf(1100,550);barh(1:length(keys),values,'FaceColor',[.4 .4 .4]);
set(gca,'Position',[.28,.16,.68,.7]);
yticks(1:length(keys));yticklabels(strrep(keys,'_',' '));xlabel('Difference / actual placed volume');
title('MODEL | hotspot: paired sand attribution at year 15');
subtitle('Counterfactual effects; includes avoided deficit; not tagged-grain probabilities');grid on;
saveplots(fig,fd,'F12_paired_sand_attribution');
J=jsondecode(fileread(fullfile(root,'MC_S2_once','summary.json')));
fig=nf(1150,600);tiledlayout(1,3,'TileSpacing','compact');fields={'p10','p50','p90'};
for k=1:3
 nexttile;imagesc(J.width_trajectory.x/1000,J.width_trajectory.t,max(J.width_trajectory.(fields{k}),0));axis xy;
 xlim([-2.5,2.5]);clim([0,ceil(max(J.width_trajectory.p90,[],'all')/5)*5]);xlabel('Alongshore coordinate (km)');ylabel('Time (yr)');
 title(['MODEL | pointwise ' fields{k}]);colorbar;
end
sgtitle('S2 once: pointwise storm uncertainty; fixed parameters','Color','k');
saveplots(fig,fd,'F13_width_spacetime_quantiles');

P=readtable(fullfile(root,'supplements','phase_runs.csv'),'TextType','string');
fig=nf(1100,500);tiledlayout(1,2,'TileSpacing','compact');strategies={'uniform','hotspot'};
for k=1:2
 nexttile;v=unique(P.volume);ws=unique(P.w_min);z=zeros(length(v),length(ws));
 for i=1:length(v)
  for j=1:length(ws)
   mask=P.strategy==strategies{k} & P.volume==v(i) & P.w_min==ws(j);
   z(i,j)=mean(P.T_safe_w(mask));
  end
 end
 imagesc(ws,v/1e6,z);axis xy;colorbar;clim([0,15]);
 xlabel('Minimum initial width (m)');ylabel('Placed sand (million m^3)');title(['MODEL | ' strategies{k}]);
end
sgtitle('S1 storms: mean length-weighted safe years, 32 shared seeds per point','Color','k');
saveplots(fig,fd,'F14_durable_phase_map');

Q=readtable(fullfile(root,'supplements','joint_runs.csv'),'TextType','string');
P=readtable(fullfile(root,'supplements','policy_runs.csv'),'TextType','string');
fig=nf(1200,600);tiledlayout(1,2,'TileSpacing','compact');nexttile;hold on;
for k=1:3
 s="S"+string(k);a=qb(Q.E_b(Q.scenario==s),[.1,.5,.9]);
 B=readtable(fullfile(root,['MC_' char(s) '_once'],'runs.csv'));b=qb(B.E_b,[.1,.5,.9]);
 errorbar(k-.1,b(2),b(2)-b(1),b(3)-b(2),'ko','LineWidth',1.4);
 errorbar(k+.1,a(2),a(2)-a(1),a(3)-a(2),'ks','MarkerFaceColor',[.5,.5,.5],'LineWidth',1.4);
end
xticks(1:3);xticklabels({'S1','S2','S3'});ylabel('Building-clearance exposure (m yr)');
title('MODEL | once: p10, median, p90');legend({'Storms only','Assumed parameters + storms'},'Location','best');grid on;
nexttile;hold on;settings=unique(P.setting,'stable');q=zeros(length(settings),3);
for k=1:length(settings),q(k,:)=qb(P.E_b(P.setting==settings(k)),[.1,.5,.9]);end
errorbar(1:length(settings),q(:,2),q(:,2)-q(:,1),q(:,3)-q(:,2),'ko','MarkerFaceColor',[.4,.4,.4]);
xticks(1:length(settings));xticklabels(strrep(settings,'_',' '));xtickangle(25);
ylabel('Building-clearance exposure (m yr)');title('MODEL | S2 adaptive: 100 shared seeds per setting');grid on;
saveplots(fig,fd,'F15_joint_and_policy_uncertainty');

J=jsondecode(fileread(fullfile(root,'S2_adaptive','results.json')));D=J.placements.adaptive_decisions;
if ~iscell(D),D=num2cell(D);end
fig=nf(1100,600);tiledlayout(2,1,'TileSpacing','compact');nexttile;hold on;
approvedT=[];approvedV=[];reviewT=[];reviewD=[];
for k=1:numel(D)
 d=D{k};
 if strcmp(d.action,'approve'),approvedT(end+1)=d.completion;approvedV(end+1)=d.best.volume/1e6;end
 if strcmp(d.action,'monitor_review'),reviewT(end+1)=d.t;reviewD(end+1)=d.relative_rmse;end
end
if ~isempty(approvedT),stem(approvedT,approvedV,'k','filled','LineWidth',1.5);end
xlim([0,15]);xlabel('Construction completion (yr)');ylabel('Placed volume (million m^3)');
title('MODEL | S2 adaptive, seed 42: realized projects after permit/build delay');grid on;
nexttile;hold on;if ~isempty(reviewT),plot(reviewT,reviewD,'ko-','LineWidth',1.3);end
yline(.30,'k--','Update threshold');xlim([0,15]);xlabel('Time (yr)');ylabel('Relative predictive RMSE');
title('SYNTHETIC SURVEY | 6/12/24-month review; mismatch has multiple possible causes');grid on;
limits=ylim;ylim([0,max(.33,limits(2)*1.05)]);
saveplots(fig,fd,'F16_adaptive_decisions_and_monitoring');
P=readtable(fullfile(root,'footprint','comparison.csv'),'TextType','string');
fig=nf(1250,470);tiledlayout(1,3,'TileSpacing','compact');names={'once','repeat','fixed_hotspot'};
commonTop=max(100,ceil(max(P.E_b_p90)*1.08/100)*100);
for k=1:3
 nexttile;S=sortrows(P(P.strategy==names{k},:),'sigma_m');
 errorbar(1:height(S),S.E_b_p50,S.E_b_p50-S.E_b_p10,S.E_b_p90-S.E_b_p50, ...
  'ko','MarkerFaceColor',[.4,.4,.4],'LineWidth',1.4);
 xticks(1:4);xticklabels({'Uniform','1 km','2 km','5 km'});xtickangle(25);
 xlim([.5,4.5]);ylim([0,commonTop]);
 ylabel('Building-clearance exposure (m yr)');title(['MODEL | ' strrep(names{k},'_',' ')]);grid on;
end
sgtitle({'S2 footprint sensitivity: 100 shared storm-mark seeds per setting', ...
 'Peak-normalized Gaussian: smaller integrated erosion; not equal storm energy'},'Color','k');
saveplots(fig,fd,'F17_storm_footprint_sensitivity');
fprintf('MATLAB: wrote 17 PNG/PDF figure pairs to %s\n',fd);
end

function fig=nf(width,height)
fig=figure('Visible','off','Color','w','Position',[100,100,width,height]);
end
function saveplots(fig,fd,name)
% R2025a desktop theme can otherwise create dark axes on a white figure.
set(fig,'Color','w');
axesList=findall(fig,'Type','axes');
for ax=axesList'
 set(ax,'Color','w','XColor','k','YColor','k','ZColor','k', ...
  'GridColor',[.65,.65,.65],'GridAlpha',.25,'XMinorGrid','off','YMinorGrid','off','YMinorTick','off');
end
set(findall(fig,'Type','text'),'Color','k');
for lg=findall(fig,'Type','legend')'
 set(lg,'Color','w','TextColor','k','EdgeColor',[.4,.4,.4]);
end
for cb=findall(fig,'Type','colorbar')',set(cb,'Color','k');end
exportgraphics(fig,fullfile(fd,[name '.png']),'Resolution',180,'BackgroundColor','white');
if ismember(name,{'F1_S2_width_heatmap','F13_width_spacetime_quantiles','F14_durable_phase_map'})
 % Vector shading creates visible stitching seams in PDF viewers. Rasterize
 % these three heatmaps at publication resolution, preserving the MATLAB view.
 exportgraphics(fig,fullfile(fd,[name '.pdf']),'ContentType','image','Resolution',300,'BackgroundColor','white');
else
 exportgraphics(fig,fullfile(fd,[name '.pdf']),'ContentType','vector','BackgroundColor','white');
end
close(fig);
end
function q=qb(values,ps)
v=sort(values(isfinite(values)));n=numel(v);q=zeros(size(ps));
for j=1:numel(ps)
 index=1+(n-1)*ps(j);lo=floor(index);hi=ceil(index);q(j)=v(lo)+(index-lo)*(v(hi)-v(lo));
end
end
