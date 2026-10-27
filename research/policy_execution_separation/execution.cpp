#define main inherited_replay_main
#include "../hypothesis_controller_search/replay.cpp"
#undef main
#include <queue>
#include "policy.hpp"
struct Mechanics {int id,lag,spacing,leglag,keep,cancelack,duplicate,interval,stale,pendingaware,bounded,ttl;};
struct Submitted {long long at,cancelat;int contract,signed_quantity,remaining,version,reason;bool bounded;string origin;int executed=0,cancelled=0,failed=0;};
struct Scheduled {long long at;int id,slice,kind;bool operator<(const Scheduled&b)const{return at>b.at||(at==b.at&&id>b.id);}};
struct FillRecord {long long second,decision;int request,j,signedq,before,after,reason,version,requested;double price;string origin;};
struct GoalRecord {long long second;int reason,version;vector<int>target;};
struct Execution : Replay {
 Mechanics m;DesiredPolicy policy;vector<Submitted>requests;priority_queue<Scheduled>events;
 vector<FillRecord>fills;vector<GoalRecord>goals;vector<vector<pair<long long,int>>>history;
 vector<long long>sign_start;vector<int>last_target;vector<vector<int>>active;int policy_id,model_id;long long now=0;int high_pending=0;
 Execution(const Cycle&data,const Config&cfg,const Calibration&cal,int a,int risk,Mechanics mechanics,int pid,int mid):Replay(data,cfg,cal),m(mechanics),policy(data,cal,a,risk),history(d.C),sign_start(d.C,-1),last_target(d.C),active(d.C),policy_id(pid),model_id(mid){}
 int time_index(long long second)const {int minute=second/60;auto where=upper_bound(d.minute.begin(),d.minute.end(),minute);int t=int(where-d.minute.begin())-1;return t>=0&&d.minute[t]==minute?t:-1;}
 void prune(int j){auto&ids=active[j];ids.erase(remove_if(ids.begin(),ids.end(),[&](int id){auto&r=requests[id];return !r.remaining||now>=r.cancelat||now-r.at>m.ttl;}),ids.end());}
 int pending_quantity(int j){prune(j);int n=0;for(int id:active[j]){auto&r=requests[id];n+=signof(r.signed_quantity)*r.remaining;}return n;}
 int pending_count(int j){prune(j);return active[j].size();}
 int stale_quantity(int j)const{auto&h=history[j];auto it=upper_bound(h.begin(),h.end(),make_pair(now-m.stale,numeric_limits<int>::max()));return it==h.begin()?0:prev(it)->second;}
 void submit(int j,int signedq,int reason,string origin,int extra_lag=0,bool forced_bound=false){
  if(!signedq)return;int t=time_index(now);if(t<0)return;
  // Base-unit order fragmentation is distinct from child partial fills.
  bool expansion=policy.target[j]!=0&&(q[j]==0||(q[j]*signedq>0&&abs(policy.target[j])>abs(q[j])));
  if(m.id==1&&expansion&&abs(signedq)>d.base){
   int units=abs(signedq)/d.base,leg=d.right[j]+(signedq>0?0:2);
   for(int k=0;k<units;k++){int id=requests.size(),amount=signof(signedq)*d.base;requests.push_back({now,numeric_limits<long long>::max(),j,amount,d.base,policy.version,reason,true,origin});active[j].push_back(id);events.push({now+m.lag+extra_lag+m.leglag*leg+m.spacing*k,id,d.base,0});}return;
  }
  int id=requests.size();requests.push_back({now,numeric_limits<long long>::max(),j,signedq,abs(signedq),policy.version,reason,forced_bound||bool(m.bounded),origin});active[j].push_back(id);
  int base=d.base,units=abs(signedq)/base;
  // Semantic leg ordering; contract-array index is not an execution priority.
  bool long_add=signedq>0&&policy.target[j]>0;bool short_cover=signedq>0&&q[j]<0&&policy.target[j]==0;
  int leg=d.right[j]+((long_add||short_cover)?0:2);
  if(m.spacing==0)events.push({now+m.lag+extra_lag+m.leglag*leg,id,abs(signedq),0});
  else for(int k=0;k<units;k++)events.push({now+m.lag+extra_lag+m.leglag*leg+m.spacing*k,id,base,0});
 }
 void reconcile(int reason=128,bool force_bound=false){
  for(int j=0;j<d.C;j++){
   if(m.id==6&&pending_count(j)>=2)continue;
   int seen=m.stale?stale_quantity(j):q[j];int pending=m.pendingaware?pending_quantity(j):0;
   int delta=policy.target[j]-seen-pending;if(delta)submit(j,delta,reason,"execution_reconciliation",0,force_bound);
  }
 }
 void changed_target(int why){
  if(m.id==3)for(auto&r:requests)if(r.remaining)r.cancelat=min(r.cancelat,now+m.cancelack);
  bool wholeflat=all_of(policy.target.begin(),policy.target.end(),[](int n){return n==0;});bool duplicated=false;
  for(int j=0;j<d.C;j++){
   int delta=policy.target[j]-q[j]-(m.pendingaware?pending_quantity(j):0);if(!delta)continue;
   submit(j,delta,why,"policy_target_delta");
   if(m.duplicate&&wholeflat&&q[j]!=0&&sign_start[j]>=0&&now-sign_start[j]>=60){submit(j,delta,why,"hypothetical_stale_duplicate",1);duplicated=true;}
  }
  if(duplicated)events.push({now+5,-1,0,1});
 }
 void process(long long until){
  while(!events.empty()&&events.top().at<=until){auto e=events.top();events.pop();now=e.at;
   if(e.kind==1){reconcile(128,true);continue;}
   if(e.kind==2){reconcile();continue;}
   auto&r=requests[e.id];if(!r.remaining)continue;int slice=min(e.slice,r.remaining);r.remaining-=slice;
   int t=time_index(now);if(t<0||now>=r.cancelat||now-r.at>m.ttl){r.cancelled+=slice;continue;}
   int signedq=signof(r.signed_quantity)*slice;
   if(r.bounded){int gap=policy.target[r.contract]-q[r.contract];if(gap*signedq<=0){r.cancelled+=slice;continue;}signedq=signof(signedq)*min(abs(gap),abs(signedq));}
   r.cancelled+=slice-abs(signedq);
   if(!signedq)continue;int old=q[r.contract];double price=d.open[t*d.C+r.contract];
   Replay::fill(t,r.contract,signedq,0,r.reason);
   if(q[r.contract]==old){r.failed+=abs(signedq);continue;}int actual=q[r.contract]-old;r.executed+=abs(actual);
   fills.push_back({now,r.at,e.id,r.contract,actual,old,q[r.contract],r.reason,r.version,r.signed_quantity,price,r.origin});
   if(!old||old*q[r.contract]<0)sign_start[r.contract]=now;else if(!q[r.contract])sign_start[r.contract]=-1;
   history[r.contract].push_back({now,q[r.contract]});
  }
  now=until;
 }
 void run_separated(const vector<GoalRecord>*frozen=nullptr){
  size_t goalpos=0;
  for(int t=0;t<d.T;t++){
   long long start=60LL*d.minute[t];process(start);now=start;
   if(frozen){while(goalpos<frozen->size()&&(*frozen)[goalpos].second==start){auto&g=(*frozen)[goalpos++];policy.target=g.target;policy.version=g.version;goals.push_back(g);changed_target(g.reason);}}
   else if(policy.update(t,q,cost,side_realized)){goals.push_back({start,policy.reason,policy.version,policy.target});changed_target(policy.reason);}
   if(m.interval)for(int s=0;s<60;s+=m.interval)events.push({start+s,-1,0,2});
   process(start+59);auto state=mark(t);path[t]={cash,realized,state[0],state[1],state[2],state[3],turnover,fees};
  }
 }
};
void augment_seeds(Cycle&d){
 if(d.phase[0]!=0)return;int t=-1;for(int i=0;i<d.T;i++)if(d.clock[i]==556&&d.session[i]==0){t=i;break;}
 if(t<0||!good(d.feature[t*8]))return;int center=int(floor(d.feature[t*8]/d.step+.5))*d.step;int distance=d.u==0?2000:(d.expiry>=20260916?2000:4000);
 vector<pair<int,int>>extra;
 for(int right=0;right<2;right++)for(int k:{center,center+(right?-distance:distance)}){bool found=false;for(int j=0;j<d.C;j++)if(d.strike[j]==k&&d.right[j]==right)found=true;if(!found)extra.push_back({k,right});}
 if(extra.empty())return;int old=d.C,newc=old+extra.size();
 auto growfloat=[&](vector<float>&v){vector<float>n(d.T*newc,NAN);for(int t=0;t<d.T;t++)copy_n(v.begin()+t*old,old,n.begin()+t*newc);v=move(n);};
 for(auto*p:{&d.prior,&d.open,&d.pvol,&d.vol,&d.delta,&d.vega,&d.gamma})growfloat(*p);
 vector<int>obs(d.T*newc),actual(d.T*newc*4);for(int t=0;t<d.T;t++)for(int j=0;j<old;j++){obs[t*newc+j]=d.observed[t*old+j];for(int r=0;r<4;r++)actual[(t*newc+j)*4+r]=d.actual[(t*old+j)*4+r];}
 d.observed=move(obs);d.actual=move(actual);for(auto x:extra){d.strike.push_back(x.first);d.right.push_back(x.second);}d.C=newc;
}
vector<Cycle> read_cycles(const string&path){
 ifstream f(path,ios::binary);auto prefix=readv<int>(f,2);if(prefix[0]!=80301)throw runtime_error("wrong canonical cache schema");vector<Cycle>out;
 for(int k=0;k<prefix[1];k++){auto z=readv<int>(f,8);Cycle d;d.id=z[0];d.u=z[1];d.split=z[2];d.T=z[3];d.C=z[4];d.base=z[5];d.step=z[6];d.expiry=z[7];d.strike=readv<int>(f,d.C);d.right=readv<int>(f,d.C);d.minute=readv<int>(f,d.T);d.clock=readv<int>(f,d.T);d.session=readv<int>(f,d.T);d.phase=readv<int>(f,d.T);d.feature=readv<double>(f,d.T*8);d.prior=readv<float>(f,d.T*d.C);d.open=readv<float>(f,d.T*d.C);d.pvol=readv<float>(f,d.T*d.C);d.vol=readv<float>(f,d.T*d.C);d.delta=readv<float>(f,d.T*d.C);d.vega=readv<float>(f,d.T*d.C);d.gamma=readv<float>(f,d.T*d.C);d.actual=readv<int>(f,d.T*d.C*4);d.observed=readv<int>(f,d.T*d.C);d.cash=readv<double>(f,d.T);augment_seeds(d);out.push_back(move(d));}return out;
}
Calibration read_calibration(const string&path){Calibration c;ifstream f(path);for(int u=0;u<2;u++)for(int ph=0;ph<2;ph++)for(int s=0;s<18;s++)for(int r=0;r<4;r++)f>>c.clock[u][ph][s][r];for(int u=0;u<2;u++)for(int ph=0;ph<2;ph++)for(int s=0;s<18;s++)for(int r=0;r<4;r++)f>>c.pool[u][ph][s][r];for(int u=0;u<2;u++)for(int r=0;r<3;r++)f>>c.cap[u][r];if(!f)throw runtime_error("bad calibration");return c;}
string booktext(const Cycle&d,const vector<int>&q){ostringstream s;s<<"[";bool comma=false;for(int j=0;j<d.C;j++)if(q[j]){if(comma)s<<";";s<<d.strike[j]<<":"<<d.right[j]<<":"<<q[j];comma=true;}s<<"]";return s.str();}
void traces(const Execution&r,ostream&fillout,ostream&goalout,ostream&requestout){
 for(auto&a:r.fills)fillout<<r.model_id<<","<<r.d.id<<","<<a.second<<","<<a.request<<","<<a.requested<<","<<abs(a.signedq)<<","<<r.d.strike[a.j]<<","<<r.d.right[a.j]<<","<<(a.signedq>0?"Buy":"Sell")<<","<<a.price<<","<<a.before<<","<<a.after<<","<<a.reason<<","<<a.version<<","<<a.origin<<","<<a.decision<<"\n";
 for(auto&a:r.goals)goalout<<r.model_id<<","<<r.d.id<<","<<a.second<<","<<a.version<<","<<a.reason<<",\""<<booktext(r.d,a.target)<<"\"\n";
 for(size_t i=0;i<r.requests.size();i++){auto&a=r.requests[i];requestout<<r.model_id<<","<<r.d.id<<","<<i<<","<<a.at<<","<<r.d.strike[a.contract]<<","<<r.d.right[a.contract]<<","<<a.signed_quantity<<","<<a.remaining<<","<<a.executed<<","<<a.cancelled<<","<<a.failed<<","<<a.version<<","<<a.bounded<<","<<a.origin<<","<<(a.cancelat==numeric_limits<long long>::max()?-1:a.cancelat)<<"\n";}
}

void compact_traces(const Execution&r,ostream&coarse,ostream&closures,ostream&audit){
 const Cycle&d=r.d;vector<long long>first(r.pred.size(),-1),last(r.pred.size(),-1);vector<int>check(r.pred.size());
 double cash=0;for(auto&f:r.fills){int t=r.time_index(f.second);int cl=f.before*f.signedq<0?min(abs(f.before),abs(f.signedq)):0,op=abs(f.signedq)-cl;
  for(auto part:{make_pair(f.signedq>0?1:3,cl),make_pair(f.signedq>0?2:0,op)})if(part.second){int cell=r.cell(t,f.j,part.first);if(first[cell]<0)first[cell]=f.second;last[cell]=f.second;check[cell]+=part.second;}
  cash-=f.signedq*f.price;
 }
 if(check!=r.pred||abs(cash-r.cash)>1e-4)throw runtime_error("simulated accounting/role mismatch");
 for(int t=0;t<d.T;t++)for(int j=0;j<d.C;j++)for(int k=0;k<4;k++){int cell=r.cell(t,j,k),q=r.pred[cell];if(q)coarse<<r.model_id<<","<<d.id<<","<<d.minute[t]<<","<<d.strike[j]<<","<<d.right[j]<<","<<k<<","<<q<<","<<first[cell]<<","<<last[cell]<<","<<d.open[t*d.C+j]<<"\n";}
 double target_area=0,zero_target_contract_seconds=0;
 auto covered=[&](long long second){int minute=second/60;auto it=lower_bound(d.minute.begin(),d.minute.end(),minute);return 60LL*(it-d.minute.begin())+(it!=d.minute.end()&&*it==minute?second%60:0);};
 for(int j=0;j<d.C;j++){auto&h=r.history[j];size_t i=0,k=0;long long last=60LL*d.minute.front();int q=0,target=0;
  while(i<h.size()||k<r.goals.size()){long long ht=i<h.size()?h[i].first:numeric_limits<long long>::max(),gt=k<r.goals.size()?r.goals[k].second:numeric_limits<long long>::max();long long now=min(ht,gt);double duration=covered(now)-covered(last);target_area+=duration*abs(q-target)/double(d.base);if(!target&&q)zero_target_contract_seconds+=duration;
   while(i<h.size()&&h[i].first==now)q=h[i++].second;while(k<r.goals.size()&&r.goals[k].second==now)target=r.goals[k++].target[j];last=now;
  }double duration=60LL*d.T-covered(last);target_area+=duration*abs(q-target)/double(d.base);if(!target&&q)zero_target_contract_seconds+=duration;
 }
 long long requested=0,executed=0,cancelled=0,failed=0,pending=0,duplicates=0,corrections=0;
 for(auto&a:r.requests){if(abs(a.signed_quantity)!=a.executed+a.cancelled+a.failed+a.remaining)throw runtime_error("request quantity conservation failed");requested+=abs(a.signed_quantity);executed+=a.executed;cancelled+=a.cancelled;failed+=a.failed;pending+=a.remaining;duplicates+=a.origin=="hypothetical_stale_duplicate";corrections+=a.origin=="execution_reconciliation";}
 audit<<r.model_id<<","<<d.id<<","<<r.requests.size()<<","<<requested<<","<<executed<<","<<cancelled<<","<<failed<<","<<pending<<","<<duplicates<<","<<corrections<<","<<r.fills.size()<<","<<target_area<<","<<zero_target_contract_seconds<<"\n";
 struct Atom{long long t;int before,after;long long age;};
 for(int j=0;j<d.C;j++){
  vector<Atom>a;auto&h=r.history[j];int previous=0;long long signstart=-1;
  for(size_t i=0;i<h.size();){size_t end=i+1;while(end<h.size()&&h[end].first==h[i].first)end++;int after=h[end-1].second;
   if((previous==0&&after!=0)||previous*after<0)signstart=h[i].first;
   a.push_back({h[i].first,previous,after,signstart<0?-1:h[i].first-signstart});previous=after;i=end;
  }
  for(size_t i=0;i<a.size();i++)if(a[i].before&&a[i].after==0&&a[i].age>=60){
   bool reopen=i+1<a.size()&&a[i+1].t-a[i].t<=10&&a[i+1].after!=0;
   bool opposite=reopen&&a[i].before*a[i+1].after<0;int peak=0;long long neutral=-1;
   if(reopen)for(size_t k=i+1;k<a.size()&&a[k].t-a[i+1].t<=60;k++){peak=max(peak,abs(a[k].after));if(opposite&&a[k].after*a[i].before>0)break;if(a[k].after==0){neutral=a[k].t;break;}}
   bool motif=opposite&&neutral>=0&&peak<=abs(a[i].before);
   closures<<r.model_id<<","<<d.id<<","<<d.strike[j]<<","<<d.right[j]<<","<<a[i].t<<","<<a[i].before<<","<<a[i].age<<","<<reopen<<","<<(reopen?a[i+1].t:-1)<<","<<(reopen?a[i+1].after:0)<<","<<peak<<","<<neutral<<","<<motif<<"\n";
  }
 }
}
#ifndef SEPARATED_TEST
int main(int argc,char**argv){try{
 if(argc<5)throw runtime_error("usage: separated CACHE CONFIGS CALIBRATION TRACE_PREFIX [frozen-policy-id]");
 auto cycles=read_cycles(argv[1]);auto cal=read_calibration(argv[3]);ifstream configs(argv[2]);string line;
 ofstream fo(string(argv[4])+"_fills.csv"),go(string(argv[4])+"_goals.csv"),ro(string(argv[4])+"_requests.csv"),io(string(argv[4])+"_inventory.csv"),co(string(argv[4])+"_coarse.csv"),cl(string(argv[4])+"_closures.csv"),au(string(argv[4])+"_request_audit.csv");
 fo<<"model_id,cycle_id,second,request_id,requested_signed_quantity,incremental_quantity,strike,right,side,price,quantity_before,quantity_after,reason,goal_version,origin,decision_second\n";
 go<<"model_id,cycle_id,second,goal_version,reason,desired_book\n";ro<<"model_id,cycle_id,request_id,decision_second,strike,right,requested_signed_quantity,unfilled_remaining,executed_quantity,cancelled_quantity,failed_quantity,goal_version,bounded,origin,cancellation_effective_second\n";
 io<<"model_id,cycle_id,minute,cash,realized,marked_equity,simulated_book,observed_book\n";
 co<<"model_id,cycle_id,minute,strike,right,action,quantity,first_second,last_second,fill_price\n";
 cl<<"model_id,cycle_id,strike,right,close_second,prior_quantity,old_sign_age_seconds,reopen_within10,reopen_second,opposite_quantity,peak_quantity,neutralized_second,conservative_motif\n";
 au<<"model_id,cycle_id,requests,requested_quantity,executed_quantity,cancelled_quantity,failed_quantity,pending_quantity,duplicate_requests,correction_requests,child_fills,target_error_base_unit_seconds,zero_target_contract_seconds\n";
 co<<setprecision(12);cout<<setprecision(12);fo<<setprecision(12);io<<setprecision(12);header(cout);
 set<int> detailed;if(argc>6){string text=argv[6];replace(text.begin(),text.end(),',',' ');istringstream list(text);int id;while(list>>id)detailed.insert(id);}
 vector<vector<GoalRecord>>frozen(cycles.size());int frozenid=argc>5?stoi(argv[5]):-1;
 if(frozenid>=0)for(auto&d:cycles){Config cfg{};cfg.id=frozenid*7;cfg.scale=1;cfg.budget=.025;cfg.partial=1;cfg.capscale=1;Mechanics safe{0,0,0,0,0,0,0,0,0,0,1,120};Execution r(d,cfg,cal,frozenid/3,frozenid%3,safe,frozenid,frozenid*7);r.run_separated();frozen[d.id]=r.goals;}
 while(getline(configs,line)){if(line.empty())continue;replace(line.begin(),line.end(),',',' ');istringstream s(line);int id,a,risk;Mechanics m;s>>id>>a>>risk>>m.id>>m.lag>>m.spacing>>m.leglag>>m.keep>>m.cancelack>>m.duplicate>>m.interval>>m.stale>>m.pendingaware>>m.bounded>>m.ttl;if(!s)throw runtime_error("bad separated model definition");
  for(auto&d:cycles){Config cfg{};cfg.id=id;cfg.scale=1;cfg.budget=.025;cfg.partial=1;cfg.capscale=1;Execution r(d,cfg,cal,a,risk,m,a*3+risk,id);r.run_separated(frozenid>=0?&frozen[d.id]:nullptr);
   for(int ph=0;ph<3;ph++){if(ph<2&&count(d.phase.begin(),d.phase.end(),ph)==0)continue;Stats st;score(r,ph,st);output(cout,r,ph,st);}compact_traces(r,co,cl,au);
   if(detailed.count(id))traces(r,fo,go,ro);else for(auto&a:r.goals)go<<r.model_id<<","<<r.d.id<<","<<a.second<<","<<a.version<<","<<a.reason<<",\""<<booktext(r.d,a.target)<<"\"\n";
   if(detailed.count(id)){vector<int>q(d.C);for(int t=0;t<d.T;t++){for(int j=0;j<d.C;j++)q[j]+=-r.pred[r.cell(t,j,0)]+r.pred[r.cell(t,j,1)]+r.pred[r.cell(t,j,2)]-r.pred[r.cell(t,j,3)];vector<int>obs(d.observed.begin()+t*d.C,d.observed.begin()+(t+1)*d.C);io<<id<<","<<d.id<<","<<d.minute[t]<<","<<r.path[t][0]<<","<<r.path[t][1]<<","<<r.path[t][2]<<",\""<<booktext(d,q)<<"\",\""<<booktext(d,obs)<<"\"\n";}}
  }
  cerr<<"Finished separated model "<<id<<"\n";
 }
 }catch(exception&e){cerr<<e.what()<<"\n";return 1;}return 0;}
#endif
